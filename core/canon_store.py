import json
from copy import deepcopy
from pathlib import Path

from core.app_paths import DATA_PROJECTS_DIR
from core.file_utils import atomic_write_json, atomic_write_text


DEFAULT_CANON_STATE = {
    "people": {},
    "resources": {},
    "hooks": [],
    "timeline": [],
}


class CanonStore:
    def __init__(self, project_name: str):
        self.project_name = project_name

    @property
    def canon_dir(self) -> Path:
        return DATA_PROJECTS_DIR / self.project_name / "canon"

    @property
    def current_state_path(self) -> Path:
        return self.canon_dir / "current_state.json"

    @property
    def events_path(self) -> Path:
        return self.canon_dir / "events.jsonl"

    @property
    def snapshots_dir(self) -> Path:
        return self.canon_dir / "snapshots"

    def load_current_state(self) -> dict:
        if not self.current_state_path.exists():
            return deepcopy(DEFAULT_CANON_STATE)
        try:
            payload = json.loads(self.current_state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return deepcopy(DEFAULT_CANON_STATE)
        return _normalize_canon_state(payload)

    def save_current_state(self, payload: dict) -> None:
        atomic_write_json(self.current_state_path, _normalize_canon_state(payload))

    def append_event(self, record: dict) -> None:
        existing = self.events_path.read_text(encoding="utf-8") if self.events_path.exists() else ""
        serialized = json.dumps(record, ensure_ascii=False)
        atomic_write_text(self.events_path, f"{existing}{serialized}\n")

    def apply_state_update(self, update: dict) -> dict:
        current = self.load_current_state()
        merged = _normalize_canon_state(current)

        for key in ("people", "resources"):
            merged[key] = _merge_mapping(merged.get(key, {}), update.get(key, {}))

        for key in ("hooks", "timeline"):
            merged[key] = _merge_sequence(merged.get(key, []), update.get(key, []))

        self.save_current_state(merged)
        return merged

    def write_snapshot(self, episode_id: str, state: dict) -> Path:
        snapshot_path = self.snapshots_dir / f"{episode_id}.json"
        atomic_write_json(snapshot_path, _normalize_canon_state(state))
        return snapshot_path


def _normalize_canon_state(payload: object) -> dict:
    normalized = deepcopy(DEFAULT_CANON_STATE)
    if not isinstance(payload, dict):
        return normalized

    for key in ("people", "resources"):
        value = payload.get(key, {})
        normalized[key] = deepcopy(value) if isinstance(value, dict) else {}

    for key in ("hooks", "timeline"):
        value = payload.get(key, [])
        normalized[key] = [item for item in value if isinstance(value, list)] if isinstance(value, list) else []

    return normalized


def _merge_mapping(base: object, update: object) -> dict:
    merged = deepcopy(base) if isinstance(base, dict) else {}
    if not isinstance(update, dict):
        return merged

    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = deepcopy(merged[key])
            nested.update(deepcopy(value))
            merged[key] = nested
        else:
            merged[key] = deepcopy(value)
    return merged


def _merge_sequence(base: object, update: object) -> list:
    merged = list(base) if isinstance(base, list) else []
    if not isinstance(update, list):
        return merged
    merged.extend(update)
    return merged
