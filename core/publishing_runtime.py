from copy import deepcopy
from datetime import datetime

from core.app_paths import DATA_PROJECTS_DIR
from core.canon_store import CanonStore
from core.chapter_source import load_chapter_source
from core.publishing_canon import finalize_publish_canon
from core.publishing_incidents import summarize_publish_attempt
from core.publishing_policy import select_runnable_job
from core.publishing_quality import evaluate_publish_source
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
        runtime = self._load_runtime()
        queue = self.store.load_queue()
        decision = self._select_job_decision(config=config, runtime=runtime, queue=queue, now=now, force=force)
        if decision.get("action") != "run_now":
            return

        job = _resolve_queue_job(queue, decision.get("job"))
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
        publish_quality = evaluate_publish_source(source_payload)
        quality_report = deepcopy(publish_quality.get("raw_report", {})) or deepcopy(publish_quality)
        self.snapshot_store.write_json_snapshot(run_id, "quality_report.json", quality_report)
        if publish_quality.get("status") != "publishable":
            last_error = "; ".join(str(item) for item in publish_quality.get("errors", []))
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
                    "publish_quality": publish_quality,
                }
            )
            return

        result = self.executor.publish_job(job=deepcopy(job), config=deepcopy(config))
        self.snapshot_store.write_json_snapshot(run_id, "publish_result.json", result)
        platform_results = result.get("platform_results", {})
        platform_config_updates = result.get("platform_config_updates", {})
        self._apply_platform_results(job, platform_results)
        self._apply_platform_config_updates(config, platform_config_updates)
        publish_summary = summarize_publish_attempt(job=job, platform_results=platform_results)
        overall_status = str(publish_summary.get("job_status", "failed"))
        last_error = str(publish_summary.get("last_error", "")).strip()
        canon_update_report = finalize_publish_canon(
            project_name=self.store.project_name,
            episode_id=str(job.get("episode_id", "")).strip(),
            overall_status=overall_status,
            job=job,
            result=result,
            source_payload=source_payload,
            canon_store=self.canon_store,
            now=now,
        )

        job["status"] = overall_status
        job["last_error"] = last_error
        runtime["status"] = str(publish_summary.get("runtime_status", "idle"))
        runtime["current_job_id"] = None
        runtime["last_run_at"] = now.isoformat()
        runtime["last_error"] = last_error
        self.store.save_config(config)
        self.store.save_queue(queue)
        self.store.save_runtime(runtime)
        self.snapshot_store.write_json_snapshot(run_id, "canon_update.json", canon_update_report)
        self.store.append_history(
            {
                "timestamp": now.isoformat(),
                "job_id": job.get("id"),
                "chapter_title": job.get("chapter_title", ""),
                "success": overall_status == "done",
                "platform_results": platform_results,
                "quality_report": quality_report,
                "publish_quality": publish_quality,
                "incident_type": publish_summary.get("incident_type", ""),
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

    def _select_job_decision(self, *, config: dict, runtime: dict, queue: list[dict], now: datetime, force: bool) -> dict:
        if force:
            if runtime["status"] in {"paused", "running"}:
                return {"action": "skip", "reason": runtime["status"], "job": None}
            for item in queue:
                if item.get("status", "pending") in {"pending", "partial_failed"}:
                    return {"action": "run_now", "reason": "", "job": item}
            return {"action": "skip", "reason": "no_job", "job": None}
        return select_runnable_job(config=config, runtime=runtime, queue=queue, now=now)


def _resolve_queue_job(queue: list[dict], selected_job: dict | None) -> dict | None:
    if not isinstance(selected_job, dict):
        return None
    selected_id = str(selected_job.get("id", "")).strip()
    if selected_id:
        for item in queue:
            if str(item.get("id", "")).strip() == selected_id:
                return item
    if selected_job in queue:
        return selected_job
    return None


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
