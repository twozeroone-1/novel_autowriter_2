from datetime import datetime

from core.automation_scheduler import is_schedule_due


def select_runnable_job(*, config: dict, runtime: dict, queue: list[dict], now: datetime) -> dict:
    if not config.get("enabled", False):
        return {"action": "skip", "reason": "disabled", "job": None}

    runtime_status = str(runtime.get("status", "idle") or "idle")
    if runtime_status == "paused":
        return {"action": "skip", "reason": "paused", "job": None}
    if runtime_status == "running":
        return {"action": "skip", "reason": "running", "job": None}

    if not is_schedule_due(config.get("schedule", {}), now=now, last_run_at=runtime.get("last_run_at")):
        return {"action": "skip", "reason": "not_due", "job": None}

    job = next((item for item in queue if item.get("status", "pending") in {"pending", "partial_failed"}), None)
    if job is None:
        return {"action": "skip", "reason": "no_job", "job": None}

    return {"action": "run_now", "reason": "", "job": job}
