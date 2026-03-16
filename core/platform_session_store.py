from pathlib import Path

from core.app_paths import DATA_PROJECTS_DIR


class PlatformSessionStore:
    def __init__(self, project_name: str):
        self.project_name = project_name

    @property
    def sessions_dir(self) -> Path:
        return DATA_PROJECTS_DIR / self.project_name / "publishing" / "sessions"

    def session_state_path(self, platform_name: str) -> Path:
        normalized = str(platform_name).strip().lower() or "platform"
        return self.sessions_dir / f"{normalized}.json"
