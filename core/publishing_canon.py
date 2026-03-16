from datetime import datetime

from core.canon_candidate import is_empty_canon_candidate, normalize_canon_candidate
from core.canon_extractor import extract_canon_update


def finalize_publish_canon(
    *,
    project_name: str,
    episode_id: str,
    overall_status: str,
    job: dict,
    result: dict,
    source_payload: dict,
    canon_store,
    now: datetime,
) -> dict:
    empty_candidate = normalize_canon_candidate({})
    if overall_status != "done" or not str(episode_id).strip():
        return {
            "status": "skipped",
            "source": "none",
            "candidate": empty_candidate,
            "error": "",
        }

    try:
        candidate, source = _resolve_candidate(
            project_name=project_name,
            job=job,
            result=result,
            source_payload=source_payload,
        )
    except Exception as exc:
        return {
            "status": "failed",
            "source": "extractor",
            "candidate": empty_candidate,
            "error": str(exc),
        }
    if is_empty_canon_candidate(candidate):
        return {
            "status": "skipped",
            "source": source,
            "candidate": candidate,
            "error": "",
        }

    candidate = _ensure_episode_timeline(candidate, episode_id)
    state = canon_store.apply_state_update(candidate)
    canon_store.append_event(
        {
            "timestamp": now.isoformat(),
            "episode_id": episode_id,
            "kind": "origin_publish_success",
            "canon_update_status": "applied",
            "canon_update_source": source,
        }
    )
    canon_store.write_snapshot(episode_id, state)
    return {
        "status": "applied",
        "source": source,
        "candidate": candidate,
        "error": "",
    }


def _resolve_candidate(*, project_name: str, job: dict, result: dict, source_payload: dict) -> tuple[dict, str]:
    for source_name, raw_candidate in (("result", result.get("canon_update")), ("job", job.get("canon_update"))):
        candidate = normalize_canon_candidate(raw_candidate)
        if not is_empty_canon_candidate(candidate):
            return candidate, source_name

    source_candidate = normalize_canon_candidate(source_payload.get("canon_update"))
    if not is_empty_canon_candidate(source_candidate):
        return source_candidate, "artifact"

    extracted = normalize_canon_candidate(
        extract_canon_update(str(source_payload.get("content", "")), project_name=project_name)
    )
    if not is_empty_canon_candidate(extracted):
        return extracted, "extractor"

    return normalize_canon_candidate({}), "none"


def _ensure_episode_timeline(candidate: dict, episode_id: str) -> dict:
    merged = normalize_canon_candidate(candidate)
    timeline = list(merged.get("timeline", []))
    if episode_id not in timeline:
        timeline.append(episode_id)
    merged["timeline"] = timeline
    return merged
