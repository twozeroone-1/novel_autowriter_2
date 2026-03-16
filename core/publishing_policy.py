from datetime import datetime


def select_runnable_job(*, queue: list[dict], allowed_platforms: set[str], now: datetime | None = None) -> dict:
    scheduled_job = select_due_scheduled_job(queue=queue, now=now)
    if scheduled_job is not None:
        return {"action": "run_now", "reason": "", "job": scheduled_job, "mode": "reconcile_scheduled"}

    for item in queue:
        if item.get("status", "pending") not in {"pending", "partial_failed"}:
            continue
        if _job_has_allowed_selected_target(item, allowed_platforms):
            return {"action": "run_now", "reason": "", "job": item, "mode": "publish"}
    return {"action": "skip", "reason": "no_job", "job": None, "mode": ""}


def _job_has_allowed_selected_target(job: dict, allowed_platforms: set[str]) -> bool:
    targets = job.get("targets")
    if not isinstance(targets, dict):
        return False
    for platform_name, target in targets.items():
        if str(platform_name) not in allowed_platforms:
            continue
        if isinstance(target, dict) and target.get("selected", False):
            return True
    return False


def select_due_scheduled_job(*, queue: list[dict], now: datetime | None) -> dict | None:
    if now is None:
        return None
    for item in queue:
        if str(item.get("status", "pending")).strip().lower() != "scheduled":
            continue
        if _job_has_due_scheduled_target(job=item, now=now):
            return item
    return None


def _job_has_due_scheduled_target(*, job: dict, now: datetime) -> bool:
    targets = job.get("targets")
    if not isinstance(targets, dict):
        return False
    for target in targets.values():
        if not isinstance(target, dict):
            continue
        if not target.get("selected", False):
            continue
        if str(target.get("status", "")).strip().lower() != "scheduled":
            continue
        reserved_at = _parse_datetime(target.get("reserved_at"))
        if reserved_at is None or reserved_at <= now:
            return True
    return False


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
