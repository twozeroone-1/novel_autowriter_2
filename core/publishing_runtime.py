from copy import deepcopy
from datetime import datetime

from core.app_paths import DATA_PROJECTS_DIR
from core.automation_scheduler import is_schedule_due
from core.canon_candidate import is_empty_canon_candidate, normalize_canon_candidate
from core.canon_extractor import extract_canon_update
from core.canon_store import CanonStore
from core.chapter_source import load_chapter_source
from core.origin_quality import validate_origin_draft
from core.publishing_store import PublishingStore
from core.run_snapshot_store import RunSnapshotStore


DEFAULT_PUBLISHING_RUNTIME_STATE = {
    "status": "idle",
    "current_job_id": None,
    "last_run_at": None,
    "last_error": "",
}


class PublishingRuntime:
    def __init__(self, store: PublishingStore, executor):
        self.store = store
        self.executor = executor
        self.snapshot_store = RunSnapshotStore(project_name=store.project_name)
        self.canon_store = CanonStore(project_name=store.project_name)

    def tick(self, now: datetime, *, force: bool = False) -> None:
        config = self.store.load_config()
        if not force and not config.get("enabled", False):
            return

        runtime = self._load_runtime()
        if runtime["status"] in {"paused", "running"}:
            return

        if not force and not is_schedule_due(config.get("schedule", {}), now=now, last_run_at=runtime.get("last_run_at")):
            return

        queue = self.store.load_queue()
        job = next((item for item in queue if item.get("status", "pending") in {"pending", "partial_failed"}), None)
        if job is None:
            return

        job["status"] = "running"
        job["attempt_count"] = int(job.get("attempt_count", 0)) + 1
        runtime["status"] = "running"
        runtime["current_job_id"] = job.get("id")
        runtime["last_error"] = ""
        self.store.save_queue(queue)
        self.store.save_runtime(runtime)

        run_id = self.snapshot_store.create_run_id(prefix="origin")
        source_payload = load_chapter_source(
            self.store.project_name,
            job.get("source_path", ""),
            episode_id=str(job.get("episode_id", "")).strip() or None,
        )
        self.snapshot_store.write_json_snapshot(
            run_id,
            "input_snapshot.json",
            {
                "job": deepcopy(job),
                "source": {
                    "path": str(source_payload.get("path", "")),
                    "title": str(source_payload.get("title", "")),
                    "episode_id": str(source_payload.get("episode_id", "")),
                    "artifact_status": str(source_payload.get("artifact_status", "")),
                },
            },
        )
        quality_report = validate_origin_draft(
            title=str(source_payload.get("title", "")),
            content=str(source_payload.get("content", "")),
        )
        self.snapshot_store.write_json_snapshot(run_id, "quality_report.json", quality_report)
        if quality_report.get("status") != "passed":
            last_error = "; ".join(str(item) for item in quality_report.get("errors", []))
            job["status"] = "failed"
            job["last_error"] = last_error
            runtime["status"] = "idle"
            runtime["current_job_id"] = None
            runtime["last_run_at"] = now.isoformat()
            runtime["last_error"] = last_error
            self.store.save_queue(queue)
            self.store.save_runtime(runtime)
            self.store.append_history(
                {
                    "timestamp": now.isoformat(),
                    "job_id": job.get("id"),
                    "chapter_title": job.get("chapter_title", ""),
                    "success": False,
                    "platform_results": {},
                    "quality_report": quality_report,
                }
            )
            return

        result = self.executor.publish_job(job=deepcopy(job), config=deepcopy(config))
        self.snapshot_store.write_json_snapshot(run_id, "publish_result.json", result)
        platform_results = result.get("platform_results", {})
        platform_config_updates = result.get("platform_config_updates", {})
        self._apply_platform_results(job, platform_results)
        self._apply_platform_config_updates(config, platform_config_updates)

        overall_status = _summarize_job_status(job)
        needs_user_action = any(
            payload.get("error_type") == "requires_user_action"
            for payload in platform_results.values()
            if isinstance(payload, dict)
        )
        last_error = next(
            (
                str(payload.get("error_text", "")).strip()
                for payload in platform_results.values()
                if isinstance(payload, dict) and str(payload.get("error_text", "")).strip()
            ),
            "",
        )
        episode_id = str(job.get("episode_id", "")).strip()
        canon_update_report = _build_canon_update_report(
            job=job,
            result=result,
            source_payload=source_payload,
            project_name=self.store.project_name,
            overall_status=overall_status,
            episode_id=episode_id,
        )

        job["status"] = overall_status
        job["last_error"] = last_error
        runtime["status"] = "paused" if needs_user_action else "idle"
        runtime["current_job_id"] = None
        runtime["last_run_at"] = now.isoformat()
        runtime["last_error"] = last_error
        self.store.save_config(config)
        self.store.save_queue(queue)
        self.store.save_runtime(runtime)
        self.snapshot_store.write_json_snapshot(run_id, "canon_update.json", canon_update_report)
        if overall_status == "done" and episode_id:
            self.canon_store.append_event(
                {
                    "timestamp": now.isoformat(),
                    "episode_id": episode_id,
                    "kind": "origin_publish_success",
                    "chapter_title": job.get("chapter_title", ""),
                    "canon_update_status": canon_update_report["status"],
                    "canon_update_source": canon_update_report["source"],
                }
            )
            if canon_update_report["status"] == "applied":
                canon_state = self.canon_store.apply_state_update(canon_update_report["candidate"])
                self.canon_store.write_snapshot(episode_id, canon_state)
        self.store.append_history(
            {
                "timestamp": now.isoformat(),
                "job_id": job.get("id"),
                "chapter_title": job.get("chapter_title", ""),
                "success": overall_status == "done",
                "platform_results": platform_results,
                "quality_report": quality_report,
                "canon_update": canon_update_report,
            }
        )

    def _load_runtime(self) -> dict:
        runtime = deepcopy(DEFAULT_PUBLISHING_RUNTIME_STATE)
        runtime.update(self.store.load_runtime())
        return runtime

    def _apply_platform_results(self, job: dict, platform_results: dict) -> None:
        targets = job.setdefault("targets", {})
        for platform_name, payload in platform_results.items():
            target = targets.setdefault(platform_name, {})
            if not isinstance(payload, dict):
                continue
            target["status"] = payload.get("status", target.get("status", "pending"))
            if payload.get("work_id"):
                target["work_id"] = payload["work_id"]
            if payload.get("episode_id"):
                target["episode_id"] = payload["episode_id"]

    def _apply_platform_config_updates(self, config: dict, platform_config_updates: dict) -> None:
        platforms = config.setdefault("platforms", {})
        for platform_name, updates in platform_config_updates.items():
            platform_config = platforms.setdefault(platform_name, {})
            if not isinstance(updates, dict):
                continue
            platform_config.update(updates)


def _summarize_job_status(job: dict) -> str:
    selected_statuses = [
        payload.get("status", "pending")
        for payload in job.get("targets", {}).values()
        if isinstance(payload, dict) and payload.get("selected")
    ]
    if not selected_statuses:
        return "failed"
    if all(status == "done" for status in selected_statuses):
        return "done"
    if any(status == "done" for status in selected_statuses):
        return "partial_failed"
    return "failed"


def _build_canon_update_report(
    *,
    job: dict,
    result: dict,
    source_payload: dict,
    project_name: str,
    overall_status: str,
    episode_id: str,
) -> dict:
    empty_candidate = normalize_canon_candidate({})
    if overall_status != "done" or not episode_id:
        return {
            "status": "skipped",
            "source": "none",
            "candidate": empty_candidate,
            "error": "",
        }

    for source_name, raw_candidate in (("result", result.get("canon_update")), ("job", job.get("canon_update"))):
        if not isinstance(raw_candidate, dict):
            continue
        candidate = normalize_canon_candidate(raw_candidate)
        if is_empty_canon_candidate(candidate):
            continue
        return {
            "status": "applied",
            "source": source_name,
            "candidate": _ensure_episode_timeline(candidate, episode_id),
            "error": "",
        }

    source_candidate = source_payload.get("canon_update")
    if isinstance(source_candidate, dict):
        candidate = normalize_canon_candidate(source_candidate)
        if not is_empty_canon_candidate(candidate):
            return {
                "status": "applied",
                "source": "artifact",
                "candidate": _ensure_episode_timeline(candidate, episode_id),
                "error": "",
            }

    content = str(source_payload.get("content", "")).strip()
    if not content:
        return {
            "status": "skipped",
            "source": "none",
            "candidate": empty_candidate,
            "error": "",
        }

    try:
        extracted = extract_canon_update(content, project_name=project_name)
    except Exception as exc:
        return {
            "status": "failed",
            "source": "extractor",
            "candidate": empty_candidate,
            "error": str(exc),
        }

    candidate = normalize_canon_candidate(extracted)
    if is_empty_canon_candidate(candidate):
        return {
            "status": "skipped",
            "source": "extractor",
            "candidate": candidate,
            "error": "",
        }

    return {
        "status": "applied",
        "source": "extractor",
        "candidate": _ensure_episode_timeline(candidate, episode_id),
        "error": "",
    }


def _ensure_episode_timeline(candidate: dict, episode_id: str) -> dict:
    merged = normalize_canon_candidate(candidate)
    timeline = list(merged.get("timeline", []))
    if episode_id not in timeline:
        timeline.append(episode_id)
    merged["timeline"] = timeline
    return merged


def run_publishing_pass(*, now: datetime, executor_factory) -> None:
    if not DATA_PROJECTS_DIR.exists():
        return

    for path in DATA_PROJECTS_DIR.iterdir():
        if not path.is_dir():
            continue
        store = PublishingStore(project_name=path.name)
        if not store.load_config().get("enabled", False):
            continue
        runtime = PublishingRuntime(store=store, executor=executor_factory(path.name))
        runtime.tick(now=now)
