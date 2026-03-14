from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

from core.app_paths import DATA_PROJECTS_DIR
from core.file_utils import atomic_write_json, atomic_write_text


class RunSnapshotStore:
    def __init__(self, project_name: str):
        self.project_name = project_name

    @property
    def runs_dir(self) -> Path:
        return DATA_PROJECTS_DIR / self.project_name / "runs"

    def create_run_id(self, prefix: str = "run") -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}_{uuid4().hex[:6]}"

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def write_json_snapshot(self, run_id: str, filename: str, payload: dict) -> Path:
        path = self.run_dir(run_id) / filename
        atomic_write_json(path, payload)
        return path

    def write_text_snapshot(self, run_id: str, filename: str, contents: str) -> Path:
        path = self.run_dir(run_id) / filename
        atomic_write_text(path, contents)
        return path
