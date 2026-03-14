import json
from copy import deepcopy
from pathlib import Path

from core.app_paths import DATA_PROJECTS_DIR
from core.file_utils import atomic_write_json, atomic_write_text


DEFAULT_AUTOMATION_CONFIG = {
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
    "context_updates": {
        "state": False,
        "summary": False,
    },
    "generation_options": {
        "include_plot": False,
        "plot_strength": "balanced",
    },
    "poll_interval_seconds": 30,
}


class AutomationStore:
    def __init__(self, project_name: str):
        self.project_name = project_name

    @property
    def automation_dir(self) -> Path:
        return DATA_PROJECTS_DIR / self.project_name / "automation"

    @property
    def config_path(self) -> Path:
        return self.automation_dir / "config.json"

    @property
    def queue_path(self) -> Path:
        return self.automation_dir / "queue.json"

    @property
    def runtime_path(self) -> Path:
        return self.automation_dir / "runtime.json"

    @property
    def history_path(self) -> Path:
        return self.automation_dir / "history.jsonl"

    def load_config(self) -> dict:
        if not self.config_path.exists():
            return deepcopy(DEFAULT_AUTOMATION_CONFIG)

        payload = self._read_json(self.config_path)
        if not isinstance(payload, dict):
            return deepcopy(DEFAULT_AUTOMATION_CONFIG)

        merged = deepcopy(DEFAULT_AUTOMATION_CONFIG)
        for key, value in payload.items():
            default_value = merged.get(key)
            if isinstance(default_value, dict) and isinstance(value, dict):
                merged[key] = default_value | value
            else:
                merged[key] = value
        return merged

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
        content = f"{existing}{serialized}\n"
        atomic_write_text(self.history_path, content)

    def load_recent_history(self, limit: int = 10) -> list[dict]:
        if not self.history_path.exists():
            return []
        lines = [line for line in self.history_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        records = [json.loads(line) for line in lines]
        return list(reversed(records[-limit:]))

    def _read_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))
