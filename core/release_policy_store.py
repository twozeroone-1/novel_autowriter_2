from copy import deepcopy
import json
from pathlib import Path

from core.app_paths import DATA_PROJECTS_DIR
from core.file_utils import atomic_write_json


DEFAULT_RELEASE_POLICY = {
    "global": {
        "max_daily_releases": 1,
        "burst_allowed": False,
        "cooldown_failures": 2,
    },
    "platforms": {
        "munpia": {
            "enabled": False,
            "default_times": ["21:00"],
            "max_daily_releases": 1,
        },
        "novelpia": {
            "enabled": False,
            "default_times": ["21:00"],
            "max_daily_releases": 1,
        },
    },
}


class ReleasePolicyStore:
    def __init__(self, project_name: str):
        self.project_name = project_name

    @property
    def policy_dir(self) -> Path:
        return DATA_PROJECTS_DIR / self.project_name / "release_policy"

    @property
    def policy_path(self) -> Path:
        return self.policy_dir / "policy.json"

    def load(self) -> dict:
        if not self.policy_path.exists():
            return deepcopy(DEFAULT_RELEASE_POLICY)
        try:
            payload = json.loads(self.policy_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return deepcopy(DEFAULT_RELEASE_POLICY)
        return _deep_merge_dicts(deepcopy(DEFAULT_RELEASE_POLICY), payload if isinstance(payload, dict) else {})

    def save(self, payload: dict) -> None:
        atomic_write_json(self.policy_path, _deep_merge_dicts(deepcopy(DEFAULT_RELEASE_POLICY), payload if isinstance(payload, dict) else {}))


def _deep_merge_dicts(base: dict, override: dict) -> dict:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged
