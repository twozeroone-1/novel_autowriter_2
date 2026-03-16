from copy import deepcopy
from datetime import datetime

from core.app_paths import DATA_PROJECTS_DIR
from core.canon_store import CanonStore
from core.chapter_source import load_chapter_source
from core.publishing_canon import finalize_publish_canon
from core.publishing_incidents import summarize_publish_attempt
from core.publishing_policy import select_runnable_job
from core.quality_gate_orchestrator import evaluate_quality_gate
from core.release_policy_engine import evaluate_release_policy
from core.release_policy_store import ReleasePolicyStore
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
        self.release_policy_store = ReleasePolicyStore(project_name=store.project_name)

    def tick(self, now: datetime, *, force: bool = False) -> None:
        config = self.store.load_config()
        runtime = self._load_runtime()
        queue = self.store.load_queue()
        decision = self._select_job_decision(config=config, runtime=runtime, queue=queue, now=now, force=force)
        if decision.get("action") != "run_now":
            self._persist_skip_runtime(runtime=runtime, decision=decision)
            return

        job = _resolve_queue_job(queue, decision.get("job"))
        if job is None:
            return
        allowed_platforms = {str(name) for name in decision.get("allowed_platforms", [])}
        active_job = _build_executor_job(job=job, allowed_platforms=allowed_platforms)

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
                "job": deepcopy(active_job),
                "policy": {
                    "allowed_platforms": sorted(allowed_platforms),
                    "blocked_platforms": deepcopy(decision.get("blocked_platforms", {})),
                    "burst_slot": bool(decision.get("burst_slot", False)),
                },
                "source": {
                    "path": str(source_payload.get("path", "")),
                    "title": str(source_payload.get("title", "")),
                    "episode_id": str(source_payload.get("episode_id", "")),
                    "artifact_status": str(source_payload.get("artifact_status", "")),
                },
            },
        )
        publish_quality = evaluate_quality_gate(
            source_payload,
            episode_plan=source_payload.get("episode_plan"),
        )
        quality_report = deepcopy(publish_quality)
        self.snapshot_store.write_json_snapshot(run_id, "quality_report.json", quality_report)
        if publish_quality.get("status") != "publishable":
            last_error = "; ".join(str(item) for item in publish_quality.get("errors", []))
            job["status"] = "failed"
            job["last_error"] = last_error
            runtime["status"] = "blocked"
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

        quality_source = _apply_quality_source_override(
            source_payload=source_payload,
            final_source=publish_quality.get("final_source"),
        )
        active_job["source_override"] = {
            "title": str(quality_source.get("title", "")),
            "content": str(quality_source.get("content", "")),
        }

        result = self.executor.publish_job(job=deepcopy(active_job), config=deepcopy(config))
        packager_report = result.get("packager_report")
        if isinstance(packager_report, dict):
            self.snapshot_store.write_json_snapshot(run_id, "packager_report.json", packager_report)
        self.snapshot_store.write_json_snapshot(run_id, "publish_result.json", result)
        platform_results = result.get("platform_results", {})
        platform_config_updates = result.get("platform_config_updates", {})
        self._apply_platform_results(job, platform_results)
        self._apply_platform_results(active_job, platform_results)
        self._apply_platform_config_updates(config, platform_config_updates)
        publish_summary = summarize_publish_attempt(job=active_job, platform_results=platform_results)
        overall_status = str(publish_summary.get("job_status", "failed"))
        runtime_status = str(publish_summary.get("runtime_status", "idle"))
        incident_type = str(publish_summary.get("incident_type", "")).strip()
        if overall_status == "done" and _has_deferred_selected_targets(job=job, allowed_platforms=allowed_platforms):
            overall_status = "partial_failed"
            runtime_status = "idle"
            incident_type = ""
        last_error = str(publish_summary.get("last_error", "")).strip()
        canon_update_report = finalize_publish_canon(
            project_name=self.store.project_name,
            episode_id=str(job.get("episode_id", "")).strip(),
            overall_status=overall_status,
            job=job,
            result=result,
            source_payload=quality_source,
            canon_store=self.canon_store,
            now=now,
        )

        job["status"] = overall_status
        job["last_error"] = last_error
        runtime["status"] = runtime_status
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
                "incident_type": incident_type,
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
            if runtime["status"] in {"paused", "running", "blocked"}:
                return {"action": "skip", "reason": runtime["status"], "job": None}
            allowed_platforms = _collect_queue_selected_platforms(queue)
            decision = select_runnable_job(queue=queue, allowed_platforms=allowed_platforms)
            return {
                **decision,
                "allowed_platforms": sorted(allowed_platforms),
                "blocked_platforms": {},
                "burst_slot": False,
                "next_runtime_status": "idle",
            }

        if not config.get("enabled", False):
            return {"action": "skip", "reason": "disabled", "job": None}

        release_policy = self._load_effective_release_policy(config=config, queue=queue)
        policy_decision = evaluate_release_policy(
            policy=release_policy,
            runtime=runtime,
            history=self.store.load_recent_history(limit=100),
            now=now,
            force=False,
            schedule=config.get("schedule"),
        )
        if policy_decision.get("action") != "run_now":
            return {**policy_decision, "job": None}

        selector_decision = select_runnable_job(
            queue=queue,
            allowed_platforms={str(name) for name in policy_decision.get("allowed_platforms", [])},
        )
        return {**policy_decision, **selector_decision}

    def _persist_skip_runtime(self, *, runtime: dict, decision: dict) -> None:
        next_runtime_status = str(decision.get("next_runtime_status", "")).strip()
        if not next_runtime_status or runtime.get("status") == next_runtime_status:
            return
        runtime["status"] = next_runtime_status
        runtime["current_job_id"] = None
        self.store.save_runtime(runtime)

    def _load_effective_release_policy(self, *, config: dict, queue: list[dict]) -> dict:
        policy = self.release_policy_store.load()
        if self.release_policy_store.policy_path.exists():
            return policy

        selected_platforms = _collect_queue_selected_platforms(queue)
        for platform_name, platform_policy in (policy.get("platforms") or {}).items():
            if str(platform_name) in selected_platforms:
                if isinstance(platform_policy, dict):
                    platform_policy["enabled"] = True
        return policy


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


def _collect_queue_selected_platforms(queue: list[dict]) -> set[str]:
    selected_platforms: set[str] = set()
    for item in queue:
        if item.get("status", "pending") not in {"pending", "partial_failed"}:
            continue
        targets = item.get("targets")
        if not isinstance(targets, dict):
            continue
        for platform_name, target in targets.items():
            if isinstance(target, dict) and target.get("selected", False):
                selected_platforms.add(str(platform_name))
    return selected_platforms


def _build_executor_job(*, job: dict, allowed_platforms: set[str]) -> dict:
    active_job = deepcopy(job)
    targets = active_job.get("targets")
    if not isinstance(targets, dict):
        return active_job
    for platform_name, target in targets.items():
        if not isinstance(target, dict):
            continue
        if str(platform_name) not in allowed_platforms:
            target["selected"] = False
    return active_job


def _has_deferred_selected_targets(*, job: dict, allowed_platforms: set[str]) -> bool:
    targets = job.get("targets")
    if not isinstance(targets, dict):
        return False
    for platform_name, target in targets.items():
        if not isinstance(target, dict):
            continue
        if not target.get("selected", False):
            continue
        if str(platform_name) not in allowed_platforms:
            return True
    return False


def _apply_quality_source_override(*, source_payload: dict, final_source: dict | None) -> dict:
    if not isinstance(final_source, dict):
        return deepcopy(source_payload)
    merged = deepcopy(source_payload)
    for field in ("title", "content"):
        value = final_source.get(field)
        if isinstance(value, str) and value.strip():
            merged[field] = value
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
