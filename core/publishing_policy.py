def select_runnable_job(*, queue: list[dict], allowed_platforms: set[str]) -> dict:
    for item in queue:
        if item.get("status", "pending") not in {"pending", "partial_failed"}:
            continue
        if _job_has_allowed_selected_target(item, allowed_platforms):
            return {"action": "run_now", "reason": "", "job": item}
    return {"action": "skip", "reason": "no_job", "job": None}


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
