from copy import deepcopy
from pathlib import Path

from core.app_paths import DATA_PROJECTS_DIR
from core.file_utils import atomic_write_json


DEFAULT_STORY_BIBLE = {
    "worldview": "여기에 작품 세계관과 배경을 정리합니다.",
    "style_guide": "여기에 문체와 서술 규칙을 정리합니다.",
    "fixed_rules": "여기에 바뀌면 안 되는 고정 설정을 정리합니다.",
    "author_intent": "",
    "forbidden_elements": "",
}


class StoryBibleStore:
    def __init__(self, project_name: str):
        self.project_name = project_name

    @property
    def story_bible_dir(self) -> Path:
        return DATA_PROJECTS_DIR / self.project_name / "story_bible"

    @property
    def story_bible_path(self) -> Path:
        return self.story_bible_dir / "story_bible.json"

    def load(self) -> dict:
        if not self.story_bible_path.exists():
            return deepcopy(DEFAULT_STORY_BIBLE)
        try:
            payload = __import__("json").loads(self.story_bible_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return deepcopy(DEFAULT_STORY_BIBLE)
        return _normalize_story_bible(payload)

    def save(self, payload: dict) -> None:
        atomic_write_json(self.story_bible_path, _normalize_story_bible(payload))

    def export_prompt_sections(self) -> str:
        story_bible = self.load()
        return (
            "[STORY BIBLE]\n"
            f"{story_bible['worldview']}\n\n"
            "[STYLE GUIDE]\n"
            f"{story_bible['style_guide']}\n\n"
            "[FIXED RULES]\n"
            f"{story_bible['fixed_rules']}"
        )


def _normalize_story_bible(payload: object) -> dict:
    normalized = deepcopy(DEFAULT_STORY_BIBLE)
    if not isinstance(payload, dict):
        return normalized

    for key, default_value in DEFAULT_STORY_BIBLE.items():
        value = payload.get(key, default_value)
        if value is None:
            normalized[key] = default_value
        elif isinstance(value, str):
            normalized[key] = value
        else:
            normalized[key] = str(value)
    return normalized
