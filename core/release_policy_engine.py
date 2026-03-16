from collections import defaultdict
from datetime import datetime

from core.automation_scheduler import is_schedule_due


def evaluate_release_policy(
    *,
    policy: dict,
    runtime: dict,
    history: list[dict],
    now: datetime,
    force: bool,
    schedule: dict | None = None,
) -> dict:
    runtime_status = str(runtime.get("status", "idle") or "idle")
    if runtime_status == "stopped":
        return _skip_decision(reason="stopped", next_runtime_status="stopped")
    if runtime_status == "paused":
        return _skip_decision(reason="paused", next_runtime_status="paused")
    if runtime_status == "blocked":
        return _skip_decision(reason="blocked", next_runtime_status="blocked")
    if runtime_status == "running":
        return _skip_decision(reason="running", next_runtime_status="running")
    if runtime_status == "cooldown" and not force:
        last_run_at = str(runtime.get("last_run_at", "")).strip() or None
        if schedule is None or not is_schedule_due(schedule, now=now, last_run_at=last_run_at):
            return _skip_decision(reason="cooldown", next_runtime_status="cooldown")

    quality_stop_threshold = max(0, int((policy.get("global") or {}).get("stop_after_quality_incidents", 0) or 0))
    if quality_stop_threshold and _count_leading_incident_type(history=history, incident_type="quality_incident") >= quality_stop_threshold:
        return _skip_decision(reason="stopped", next_runtime_status="stopped")

    platform_counts = _collect_today_platform_success_counts(history=history, now=now)
    blocked_for_incidents = _collect_platform_incident_blocks(
        history=history,
        threshold=max(
            0,
            int((policy.get("global") or {}).get("block_platform_after_platform_incidents", 0) or 0),
        ),
    )
    allowed_platforms: list[str] = []
    blocked_platforms: dict[str, str] = {}
    burst_slot = False

    for platform_name, platform_policy in (policy.get("platforms") or {}).items():
        if str(platform_name) in blocked_for_incidents:
            blocked_platforms[str(platform_name)] = blocked_for_incidents[str(platform_name)]
            continue
        allowed, reason, uses_burst_slot = _platform_is_allowed_now(
            policy=policy,
            platform_name=str(platform_name),
            platform_policy=platform_policy if isinstance(platform_policy, dict) else {},
            success_count=platform_counts.get(str(platform_name), 0),
            now=now,
        )
        if allowed:
            allowed_platforms.append(str(platform_name))
            burst_slot = burst_slot or uses_burst_slot
        else:
            blocked_platforms[str(platform_name)] = reason

    if not allowed_platforms:
        return _skip_decision(
            reason="no_allowed_platforms",
            next_runtime_status="idle",
            blocked_platforms=blocked_platforms,
        )

    return {
        "action": "run_now",
        "reason": "",
        "allowed_platforms": allowed_platforms,
        "blocked_platforms": blocked_platforms,
        "burst_slot": burst_slot,
        "next_runtime_status": "idle",
    }


def _collect_today_platform_success_counts(*, history: list[dict], now: datetime) -> dict[str, int]:
    counts: defaultdict[str, int] = defaultdict(int)
    for record in history:
        timestamp = _parse_datetime(record.get("timestamp"))
        if timestamp is None or _to_comparable_date(timestamp, now) != _to_comparable_date(now, now):
            continue
        platform_results = record.get("platform_results")
        if not isinstance(platform_results, dict):
            continue
        for platform_name, result in platform_results.items():
            if isinstance(result, dict) and result.get("success") is True:
                counts[str(platform_name)] += 1
    return dict(counts)


def _count_leading_incident_type(*, history: list[dict], incident_type: str) -> int:
    count = 0
    for record in history:
        if str(record.get("incident_type", "")).strip() != incident_type:
            break
        count += 1
    return count


def _collect_platform_incident_blocks(*, history: list[dict], threshold: int) -> dict[str, str]:
    if threshold <= 0:
        return {}

    streaks: defaultdict[str, int] = defaultdict(int)
    resolved: set[str] = set()
    blocked: dict[str, str] = {}
    for record in history:
        if str(record.get("incident_type", "")).strip() != "platform_incident":
            break
        platform_results = record.get("platform_results")
        if not isinstance(platform_results, dict):
            continue
        for platform_name, payload in platform_results.items():
            name = str(platform_name)
            if name in resolved:
                continue
            if isinstance(payload, dict) and payload.get("success") is True:
                resolved.add(name)
                streaks.pop(name, None)
                continue
            streaks[name] += 1
            if streaks[name] >= threshold:
                blocked[name] = "incident_threshold_reached"
    return blocked


def _platform_is_allowed_now(
    *,
    policy: dict,
    platform_name: str,
    platform_policy: dict,
    success_count: int,
    now: datetime,
) -> tuple[bool, str, bool]:
    if not platform_policy.get("enabled", False):
        return False, "platform_disabled", False

    if not _matches_platform_time_window(platform_policy=platform_policy, now=now):
        return False, "outside_release_window", False

    requested_cap = max(1, int(platform_policy.get("max_daily_releases", 1) or 1))
    burst_allowed = bool((policy.get("global") or {}).get("burst_allowed", False))
    effective_cap = min(requested_cap, 2 if burst_allowed else 1)
    if success_count >= effective_cap:
        return False, "daily_limit_reached", False

    return True, "", _is_second_slot_open(
        burst_allowed=burst_allowed,
        requested_cap=requested_cap,
        success_count=success_count,
    )


def _is_second_slot_open(*, burst_allowed: bool, requested_cap: int, success_count: int) -> bool:
    return burst_allowed and requested_cap >= 2 and success_count >= 1


def _matches_platform_time_window(*, platform_policy: dict, now: datetime) -> bool:
    raw_times = platform_policy.get("default_times", [])
    if isinstance(raw_times, str):
        raw_times = [raw_times]
    if not isinstance(raw_times, list):
        return True
    normalized_times = [str(value).strip() for value in raw_times if str(value).strip()]
    if not normalized_times:
        return True
    return now.strftime("%H:%M") in normalized_times


def _skip_decision(
    *,
    reason: str,
    next_runtime_status: str,
    blocked_platforms: dict[str, str] | None = None,
) -> dict:
    return {
        "action": "skip",
        "reason": reason,
        "allowed_platforms": [],
        "blocked_platforms": blocked_platforms or {},
        "burst_slot": False,
        "next_runtime_status": next_runtime_status,
    }


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _to_comparable_date(value: datetime, reference: datetime) -> datetime.date:
    if value.tzinfo is not None and reference.tzinfo is not None:
        return value.astimezone(reference.tzinfo).date()
    return value.date()
