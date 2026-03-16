import json
from pathlib import Path

from core.file_utils import atomic_write_json


DEFAULT_STORY_BIBLE_SHADOW = {
    "worldview": "여기에 세계관(STORY_BIBLE)을 작성해 주세요.",
    "tone_and_manner": "여기에 문체(STYLE_GUIDE) 지침을 작성해 주세요.",
    "continuity": "여기에 절대 변경 불가 룰, 연표, 관계도(CONTINUITY)를 작성하세요.",
}


def load_raw_config_payload(config_path: Path) -> dict:
    if not config_path.exists():
        return DEFAULT_STORY_BIBLE_SHADOW.copy()

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ContextManager] Failed to load {config_path}: {exc}")
        return DEFAULT_STORY_BIBLE_SHADOW.copy()

    if not isinstance(payload, dict):
        print(f"[ContextManager] Invalid config shape at {config_path}: expected object")
        return DEFAULT_STORY_BIBLE_SHADOW.copy()
    return payload.copy()


def normalize_story_bible_shadow_payload(payload: dict | list) -> dict:
    merged = DEFAULT_STORY_BIBLE_SHADOW.copy()
    if not isinstance(payload, dict):
        return merged

    for key, default_value in DEFAULT_STORY_BIBLE_SHADOW.items():
        value = payload.get(key, default_value)
        if value is None:
            merged[key] = default_value
        else:
            merged[key] = value if isinstance(value, str) else str(value)
    return merged


def load_story_bible_shadow_payload(config_path: Path) -> dict:
    return normalize_story_bible_shadow_payload(load_raw_config_payload(config_path))


def write_story_bible_shadow_payload(config_path: Path, payload: dict) -> None:
    merged = load_raw_config_payload(config_path)
    merged.update(normalize_story_bible_shadow_payload(payload))
    atomic_write_json(config_path, merged)


def write_story_bible_shadow(
    config_path: Path,
    *,
    worldview: str,
    tone_and_manner: str,
    continuity: str,
) -> None:
    shadow_payload = load_story_bible_shadow_payload(config_path)
    shadow_payload["worldview"] = str(worldview)
    shadow_payload["tone_and_manner"] = str(tone_and_manner)
    shadow_payload["continuity"] = str(continuity)
    write_story_bible_shadow_payload(config_path, shadow_payload)
