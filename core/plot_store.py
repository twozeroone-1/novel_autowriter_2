from copy import deepcopy
from pathlib import Path

from core.app_paths import DATA_PROJECTS_DIR
from core.file_utils import atomic_write_json


DEFAULT_PLOT = {
    "plot_outline": "",
    "plot_version": "0",
}


class PlotStore:
    def __init__(self, project_name: str):
        self.project_name = project_name

    @property
    def plot_path(self) -> Path:
        return DATA_PROJECTS_DIR / self.project_name / "plot.json"

    def load(self) -> dict:
        if not self.plot_path.exists():
            return deepcopy(DEFAULT_PLOT)
        try:
            payload = __import__("json").loads(self.plot_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return deepcopy(DEFAULT_PLOT)
        return _normalize_plot(payload)

    def save(self, payload: dict) -> None:
        atomic_write_json(self.plot_path, _normalize_plot(payload))

    def bump_version(self, plot_outline: str) -> dict:
        payload = self.load()
        current_version_raw = payload.get("plot_version", "0")
        try:
            current_version = int(str(current_version_raw))
        except (TypeError, ValueError):
            current_version = 0

        updated = {
            "plot_outline": str(plot_outline).strip(),
            "plot_version": str(current_version + 1),
        }
        self.save(updated)
        return updated


def _normalize_plot(payload: object) -> dict:
    normalized = deepcopy(DEFAULT_PLOT)
    if not isinstance(payload, dict):
        return normalized

    for key, default_value in DEFAULT_PLOT.items():
        value = payload.get(key, default_value)
        if value is None:
            normalized[key] = default_value
        elif isinstance(value, str):
            normalized[key] = value
        else:
            normalized[key] = str(value)
    return normalized
