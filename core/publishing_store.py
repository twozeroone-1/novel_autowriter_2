import json
from copy import deepcopy
from pathlib import Path

from core.app_paths import DATA_PROJECTS_DIR
from core.file_utils import atomic_write_json, atomic_write_text


DEFAULT_PUBLISHING_CONFIG = {
    "enabled": False,
    "schedule": {
        "type": "daily",
        "time": "21:00",
        "days": [],
        "hours": 24,
    },
    "retry_policy": {
        "max_attempts": 2,
    },
    "browser": {
        "headless": False,
    },
    "platforms": {
        "munpia": {
            "enabled": False,
            "work_id": "",
            "work_title": "",
            "work_description": "",
            "genre": "",
            "cover_path": "",
            "create_work_url": "",
            "upload_url_template": "",
            "selectors": {},
            "default_publish_visibility": "public",
            "default_age_grade": "general",
        },
        "novelpia": {
            "enabled": False,
            "work_id": "",
            "work_title": "",
            "work_description": "",
            "genre": "",
            "cover_path": "",
            "create_work_url": "",
            "upload_url_template": "",
            "selectors": {},
            "default_publish_visibility": "public",
            "default_age_grade": "general",
        },
    },
}


class PublishingStore:
    def __init__(self, project_name: str):
        self.project_name = project_name

    @property
    def publishing_dir(self) -> Path:
        return DATA_PROJECTS_DIR / self.project_name / "publishing"

    @property
    def config_path(self) -> Path:
        return self.publishing_dir / "config.json"

    @property
    def queue_path(self) -> Path:
        return self.publishing_dir / "queue.json"

    @property
    def runtime_path(self) -> Path:
        return self.publishing_dir / "runtime.json"

    @property
    def history_path(self) -> Path:
        return self.publishing_dir / "history.jsonl"

    def load_config(self) -> dict:
        self.ensure_config_exists()
        if not self.config_path.exists():
            return deepcopy(DEFAULT_PUBLISHING_CONFIG)
        return _deep_merge_dicts(deepcopy(DEFAULT_PUBLISHING_CONFIG), self._read_json(self.config_path))

    def ensure_config_exists(self) -> None:
        self.publishing_dir.mkdir(parents=True, exist_ok=True)
        if self.config_path.exists():
            return
        atomic_write_json(self.config_path, deepcopy(DEFAULT_PUBLISHING_CONFIG))

    def save_config(self, config: dict) -> None:
        atomic_write_json(self.config_path, config)

    def load_queue(self) -> list[dict]:
        if not self.queue_path.exists():
            return []
        payload = self._read_json(self.queue_path)
        return payload if isinstance(payload, list) else []

    def save_queue(self, jobs: list[dict]) -> None:
        atomic_write_json(self.queue_path, jobs)

    def load_runtime(self) -> dict:
        if not self.runtime_path.exists():
            return {}
        payload = self._read_json(self.runtime_path)
        return payload if isinstance(payload, dict) else {}

    def save_runtime(self, runtime: dict) -> None:
        atomic_write_json(self.runtime_path, runtime)

    def append_history(self, record: dict) -> None:
        existing = self.history_path.read_text(encoding="utf-8") if self.history_path.exists() else ""
        serialized = json.dumps(record, ensure_ascii=False)
        atomic_write_text(self.history_path, f"{existing}{serialized}\n")

    def load_recent_history(self, limit: int = 10) -> list[dict]:
        if not self.history_path.exists():
            return []
        lines = [line for line in self.history_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        records = [json.loads(line) for line in lines]
        return list(reversed(records[-limit:]))

    def _read_json(self, path: Path) -> dict | list:
        return json.loads(path.read_text(encoding="utf-8"))


def _deep_merge_dicts(base: dict, override: dict) -> dict:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged
