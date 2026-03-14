from copy import deepcopy
from pathlib import Path

from core.app_paths import DATA_PROJECTS_DIR
from core.file_utils import atomic_write_json


DEFAULT_CONTEXT_STATE = {
    "state": "여기에 현재 회차 떡밥, 갈등 상황, 감정선(STATE)을 작성하세요.",
    "summary_of_previous": "여기에 지난 줄거리 요약이 누적됩니다.",
}


class ContextStateStore:
    def __init__(self, project_name: str):
        self.project_name = project_name

    @property
    def context_state_path(self) -> Path:
        return DATA_PROJECTS_DIR / self.project_name / "context_state.json"

    def load(self) -> dict:
        if not self.context_state_path.exists():
            return deepcopy(DEFAULT_CONTEXT_STATE)
        try:
            payload = __import__("json").loads(self.context_state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return deepcopy(DEFAULT_CONTEXT_STATE)
        return _normalize_context_state(payload)

    def save(self, payload: dict) -> None:
        atomic_write_json(self.context_state_path, _normalize_context_state(payload))


def _normalize_context_state(payload: object) -> dict:
    normalized = deepcopy(DEFAULT_CONTEXT_STATE)
    if not isinstance(payload, dict):
        return normalized

    for key, default_value in DEFAULT_CONTEXT_STATE.items():
        value = payload.get(key, default_value)
        if value is None:
            normalized[key] = default_value
        elif isinstance(value, str):
            normalized[key] = value
        else:
            normalized[key] = str(value)
    return normalized
