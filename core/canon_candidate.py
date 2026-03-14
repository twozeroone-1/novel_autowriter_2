from copy import deepcopy
from typing import Any

from core.canon_store import DEFAULT_CANON_STATE


def normalize_canon_candidate(payload: object) -> dict[str, Any]:
    normalized = deepcopy(DEFAULT_CANON_STATE)
    if not isinstance(payload, dict):
        return normalized

    for key in ("people", "resources"):
        value = payload.get(key, {})
        normalized[key] = deepcopy(value) if isinstance(value, dict) else {}

    for key in ("hooks", "timeline"):
        value = payload.get(key, [])
        normalized[key] = deepcopy(value) if isinstance(value, list) else []

    return normalized


def is_empty_canon_candidate(candidate: dict[str, Any]) -> bool:
    return (
        not candidate.get("people")
        and not candidate.get("resources")
        and not candidate.get("hooks")
        and not candidate.get("timeline")
    )


def build_canon_candidate_record(result: dict[str, Any]) -> dict[str, Any]:
    raw_candidate = result.get("canon_update")
    if not isinstance(raw_candidate, dict):
        return {
            "status": "missing",
            "candidate": normalize_canon_candidate({}),
        }

    candidate = normalize_canon_candidate(raw_candidate)
    if is_empty_canon_candidate(candidate):
        return {
            "status": "empty",
            "candidate": candidate,
        }

    return {
        "status": "recorded",
        "candidate": candidate,
    }
