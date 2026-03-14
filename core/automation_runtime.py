from copy import deepcopy
from datetime import datetime
from typing import Any

from core.app_paths import DATA_PROJECTS_DIR
from core.canon_candidate import build_canon_candidate_record
from core.automation_scheduler import is_schedule_due
from core.automation_store import AutomationStore


DEFAULT_RUNTIME_STATE = {
    "status": "idle",
    "current_job_id": None,
    "last_run_at": None,
    "last_error": "",
    "last_context_update_status": "",
    "last_context_update_error": "",
}


class AutomationRuntime:
    def __init__(self, store: AutomationStore, automator: Any):
        self.store = store
        self.automator = automator

    def tick(self, now: datetime) -> None:
        config = self.store.load_config()
        if not config.get("enabled", False):
            return

        runtime = self._load_runtime()
        if runtime["status"] in {"paused", "running"}:
            return

        if not is_schedule_due(config.get("schedule", {}), now=now, last_run_at=runtime.get("last_run_at")):
            return

        queue = self.store.load_queue()
        job = next((item for item in queue if item.get("status", "pending") == "pending"), None)
        if job is None:
            return

        job["status"] = "running"
        runtime["status"] = "running"
        runtime["current_job_id"] = job.get("id")
        runtime["last_error"] = ""
        runtime["last_context_update_status"] = ""
        runtime["last_context_update_error"] = ""
        self.store.save_queue(queue)
        self.store.save_runtime(runtime)

        max_attempts = int(config.get("retry_policy", {}).get("max_attempts", 2))
        generation_options = config.get("generation_options", {})
        include_plot = bool(generation_options.get("include_plot", False))
        plot_strength = str(generation_options.get("plot_strength", "balanced") or "balanced")
        last_error = ""
        for _ in range(max_attempts):
            job["attempt_count"] = int(job.get("attempt_count", 0)) + 1
            try:
                result = self.automator.run_single_cycle(
                    chapter_title=job.get("title", ""),
                    instruction=job.get("instruction", ""),
                    target_length=int(job.get("target_length", 5000)),
                    include_plot=include_plot,
                    plot_strength=plot_strength,
                )
                context_update = self._process_context_updates(result, config)
                job["status"] = "done"
                runtime["status"] = "idle"
                runtime["current_job_id"] = None
                runtime["last_run_at"] = now.isoformat()
                runtime["last_error"] = ""
                runtime["last_context_update_status"] = context_update["legacy"]["status"]
                runtime["last_context_update_error"] = context_update["legacy"].get("error", "")
                self.store.save_queue(queue)
                self.store.save_runtime(runtime)
                self.store.append_history(
                    {
                        "timestamp": now.isoformat(),
                        "job_id": job.get("id"),
                        "title": job.get("title", ""),
                        "success": True,
                        "saved_path": result.get("saved_path", ""),
                        "context_update": context_update,
                    }
                )
                return
            except Exception as exc:
                last_error = str(exc)

        job["status"] = "failed"
        runtime["status"] = "paused"
        runtime["current_job_id"] = None
        runtime["last_error"] = last_error
        self.store.save_queue(queue)
        self.store.save_runtime(runtime)
        self.store.append_history(
            {
                "timestamp": now.isoformat(),
                "job_id": job.get("id"),
                "title": job.get("title", ""),
                "success": False,
                "error_text": last_error,
            }
        )

    def _process_context_updates(self, result: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        legacy = self._apply_legacy_context_updates(result, config)
        canon_candidate = build_canon_candidate_record(result)
        return {
            "status": legacy["status"],
            "legacy": legacy,
            "canon_candidate": canon_candidate,
        }

    def _apply_legacy_context_updates(self, result: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        context_config = config.get("context_updates", {})
        apply_state = bool(context_config.get("state", True))
        apply_summary = bool(context_config.get("summary", True))
        next_state = result.get("new_state") if apply_state else None
        next_summary = result.get("new_summary") if apply_summary else None

        if next_state is None and next_summary is None:
            return {
                "status": "skipped",
                "applied": {
                    "state": False,
                    "summary_of_previous": False,
                },
            }

        try:
            applied = self.automator.apply_context_updates(
                state=next_state,
                summary_of_previous=next_summary,
            )
        except Exception as exc:
            return {
                "status": "partial_failure",
                "error": str(exc),
                "applied": {
                    "state": False,
                    "summary_of_previous": False,
                },
            }

        return {
            "status": "applied",
            "backup": applied.get("backup", {}),
            "applied": applied.get("applied", {}),
        }

    def _load_runtime(self) -> dict:
        runtime = deepcopy(DEFAULT_RUNTIME_STATE)
        runtime.update(self.store.load_runtime())
        return runtime


def run_automation_pass(
    *,
    now: datetime,
    automator_factory,
) -> None:
    if not DATA_PROJECTS_DIR.exists():
        return

    for path in DATA_PROJECTS_DIR.iterdir():
        if not path.is_dir():
            continue
        store = AutomationStore(project_name=path.name)
        if not store.load_config().get("enabled", False):
            continue
        runtime = AutomationRuntime(store=store, automator=automator_factory(path.name))
        runtime.tick(now=now)
