from pathlib import Path

from core.context_state_store import DEFAULT_CONTEXT_STATE
from core.context_story_bible_shadow import DEFAULT_STORY_BIBLE_SHADOW, load_raw_config_payload
from core.file_utils import atomic_write_json


def load_state_shadow_snapshot(config_path: Path) -> dict:
    config = load_raw_config_payload(config_path)
    snapshot = DEFAULT_CONTEXT_STATE.copy()
    for key, default_value in DEFAULT_CONTEXT_STATE.items():
        value = config.get(key, default_value)
        if value is None:
            snapshot[key] = default_value
        else:
            snapshot[key] = value if isinstance(value, str) else str(value)
    return snapshot


def write_legacy_state_shadow(
    config_path: Path,
    *,
    state: str | None = None,
    summary_of_previous: str | None = None,
) -> None:
    config = load_raw_config_payload(config_path)
    if not config:
        config = DEFAULT_STORY_BIBLE_SHADOW.copy()
    if state is not None:
        config["state"] = str(state)
    if summary_of_previous is not None:
        config["summary_of_previous"] = str(summary_of_previous)
    atomic_write_json(config_path, config)
