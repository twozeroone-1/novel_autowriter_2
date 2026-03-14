import json
from pathlib import Path

from core.app_paths import DATA_PROJECTS_DIR
from core.canon_store import CanonStore
from core.context_state_store import DEFAULT_CONTEXT_STATE, ContextStateStore
from core.file_utils import atomic_write_json
from core.plot_store import DEFAULT_PLOT, PlotStore
from core.release_policy_store import ReleasePolicyStore
from core.story_bible_store import DEFAULT_STORY_BIBLE, StoryBibleStore


BASE_DATA_DIR = DATA_PROJECTS_DIR
DEFAULT_CONFIG = {
    "worldview": "여기에 세계관(STORY_BIBLE)을 작성해 주세요.",
    "tone_and_manner": "여기에 문체(STYLE_GUIDE) 지침을 작성해 주세요.",
    "continuity": "여기에 절대 변경 불가 룰, 연표, 관계도(CONTINUITY)를 작성하세요.",
}


class ContextManager:
    def __init__(self, project_name: str = "default_project"):
        self.project_name = project_name
        self.data_dir = BASE_DATA_DIR / self.project_name
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "chapters").mkdir(exist_ok=True)
        self.story_bible_store = StoryBibleStore(project_name=project_name)
        self.canon_store = CanonStore(project_name=project_name)
        self.context_state_store = ContextStateStore(project_name=project_name, base_dir=BASE_DATA_DIR)
        self.plot_store = PlotStore(project_name=project_name)
        self.release_policy_store = ReleasePolicyStore(project_name=project_name)

        self.config_path = self.data_dir / "config.json"
        self.chars_path = self.data_dir / "characters.json"
        self._ensure_default_files()

    def _ensure_default_files(self) -> None:
        if not self.config_path.exists():
            atomic_write_json(self.config_path, DEFAULT_CONFIG.copy())
        if not self.chars_path.exists():
            self.save_characters([])

    def _default_value_for(self, path: Path) -> dict | list:
        if path.name == "config.json":
            return DEFAULT_CONFIG.copy()
        return []

    def _load_json(self, path: Path) -> dict | list:
        if not path.exists():
            return self._default_value_for(path)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[ContextManager] Failed to load {path}: {exc}")
            return self._default_value_for(path)

        if path.name == "config.json" and not isinstance(data, dict):
            print(f"[ContextManager] Invalid config shape at {path}: expected object")
            return DEFAULT_CONFIG.copy()

        if path.name != "config.json" and not isinstance(data, list):
            print(f"[ContextManager] Invalid characters shape at {path}: expected array")
            return []

        return data

    def _normalize_config(self, config: dict | list) -> dict:
        merged = DEFAULT_CONFIG.copy()
        if not isinstance(config, dict):
            return merged

        for key, default_value in DEFAULT_CONFIG.items():
            value = config.get(key, default_value)
            if value is None:
                merged[key] = default_value
            else:
                merged[key] = value if isinstance(value, str) else str(value)
        return merged

    def _load_normalized_config(self) -> dict:
        return self._normalize_config(self._load_json(self.config_path))

    def _load_raw_config_payload(self) -> dict:
        payload = self._load_json(self.config_path)
        if isinstance(payload, dict):
            return payload.copy()
        return {}

    def _merge_story_bible_into_config(self, config: dict) -> dict:
        merged = DEFAULT_CONFIG.copy()
        merged.update(config)
        if not self.story_bible_store.story_bible_path.exists():
            return merged

        story_bible = self.story_bible_store.load()

        if story_bible.get("worldview") != DEFAULT_STORY_BIBLE["worldview"] or merged["worldview"] == DEFAULT_CONFIG["worldview"]:
            merged["worldview"] = story_bible.get("worldview", merged["worldview"])
        if story_bible.get("style_guide") != DEFAULT_STORY_BIBLE["style_guide"] or merged["tone_and_manner"] == DEFAULT_CONFIG["tone_and_manner"]:
            merged["tone_and_manner"] = story_bible.get("style_guide", merged["tone_and_manner"])
        if story_bible.get("fixed_rules") != DEFAULT_STORY_BIBLE["fixed_rules"] or merged["continuity"] == DEFAULT_CONFIG["continuity"]:
            merged["continuity"] = story_bible.get("fixed_rules", merged["continuity"])

        return merged

    def _write_legacy_config(self, config: dict) -> None:
        merged = self._load_raw_config_payload()
        merged.update(self._normalize_config(config))
        atomic_write_json(self.config_path, merged)

    def _load_plot_payload(self) -> dict:
        if self.plot_store.plot_path.exists():
            return self.plot_store.load()

        config = self._load_raw_config_payload()
        return {
            "plot_outline": str(config.get("plot_outline", DEFAULT_PLOT["plot_outline"])),
            "plot_version": str(config.get("plot_version", DEFAULT_PLOT["plot_version"])),
        }

    def _write_legacy_plot_shadow(self, payload: dict) -> None:
        config = self._load_raw_config_payload()
        if not config:
            config = DEFAULT_CONFIG.copy()
        config["plot_outline"] = str(payload.get("plot_outline", ""))
        config["plot_version"] = str(payload.get("plot_version", "0"))
        atomic_write_json(self.config_path, config)

    def _write_legacy_state_shadow(
        self,
        *,
        state: str | None = None,
        summary_of_previous: str | None = None,
    ) -> None:
        config = self._load_raw_config_payload()
        if not config:
            config = DEFAULT_CONFIG.copy()
        if state is not None:
            config["state"] = str(state)
        if summary_of_previous is not None:
            config["summary_of_previous"] = str(summary_of_previous)
        atomic_write_json(self.config_path, config)

    def _get_story_bible_prompt_fields(self) -> dict[str, str]:
        story_bible = self.story_bible_store.load()
        return {
            "worldview": str(story_bible.get("worldview", DEFAULT_STORY_BIBLE["worldview"])),
            "tone_and_manner": str(story_bible.get("style_guide", DEFAULT_STORY_BIBLE["style_guide"])),
            "continuity": str(story_bible.get("fixed_rules", DEFAULT_STORY_BIBLE["fixed_rules"])),
        }

    def _get_state_snapshot(self) -> dict[str, str]:
        if self.context_state_store.context_state_path.exists():
            return self.context_state_store.load()
        config = self._load_raw_config_payload()
        snapshot = DEFAULT_CONTEXT_STATE.copy()
        for key, default_value in DEFAULT_CONTEXT_STATE.items():
            value = config.get(key, default_value)
            if value is None:
                snapshot[key] = default_value
            else:
                snapshot[key] = value if isinstance(value, str) else str(value)
        return snapshot

    def _normalize_character(self, raw_char: object) -> dict | None:
        if not isinstance(raw_char, dict):
            return None

        required_string_fields = ("id", "name", "role", "description")
        normalized: dict[str, object] = {}
        for field in required_string_fields:
            value = raw_char.get(field)
            if value is None:
                return None
            text = value if isinstance(value, str) else str(value)
            if not text.strip():
                return None
            normalized[field] = text

        traits = raw_char.get("traits")
        if not isinstance(traits, list):
            return None
        normalized_traits: list[str] = []
        for item in traits:
            text = item if isinstance(item, str) else str(item)
            if text.strip():
                normalized_traits.append(text)
        normalized["traits"] = normalized_traits
        return normalized

    def _normalize_characters(self, chars: list | dict) -> list[dict]:
        if not isinstance(chars, list):
            return []

        normalized: list[dict] = []
        for index, raw_char in enumerate(chars):
            normalized_char = self._normalize_character(raw_char)
            if normalized_char is None:
                print(f"[ContextManager] Skipping invalid character at index {index}")
                continue
            normalized.append(normalized_char)
        return normalized

    def get_worldview_context(self) -> str:
        prompt_fields = self._get_story_bible_prompt_fields()
        worldview = prompt_fields.get("worldview", "")
        tone = prompt_fields.get("tone_and_manner", "")
        return f"""[STORY BIBLE] (세계관 및 기본 설정)
{worldview}

[STYLE GUIDE] (문체 및 작성 지침)
{tone}
"""

    def get_continuity_context(self) -> str:
        continuity = self._get_story_bible_prompt_fields().get("continuity", "")
        return f"""[CONTINUITY] (고정 설정, 절대 바뀌면 안 되는 규칙)
{continuity}
"""

    def get_canon_context(self) -> str:
        canon_state = self.canon_store.load_current_state()
        return f"""[CANON FACTS] (발행 완료 회차 기준 확정 사실)
{json.dumps(canon_state, ensure_ascii=False, indent=2)}
"""

    def get_release_policy_context(self) -> str:
        release_policy = self.release_policy_store.load()
        return f"""[RELEASE POLICY] (플랫폼별 발행 정책)
{json.dumps(release_policy, ensure_ascii=False, indent=2)}
"""

    def get_state_context(self) -> str:
        state_snapshot = self._get_state_snapshot()
        state_info = state_snapshot.get("state", "")
        prev_summary = state_snapshot.get("summary_of_previous", "")
        return f"""[STATE] (현재 회차 상태, 갈등, 감정선)
{state_info}

[PREVIOUS_SUMMARY] (이전 줄거리 요약)
{prev_summary}
"""

    def get_character_context(self) -> str:
        chars_data = self.get_characters()
        if not chars_data:
            return "[등장인물 정보 없음]"

        lines = ["[주요 등장인물 프로필]"]
        for char in chars_data:
            traits = ", ".join(char.get("traits", []))
            lines.append(f"- {char['name']} ({char['role']}): {char['description']} (특징: {traits})")
        return "\n".join(lines)

    def get_config(self) -> dict:
        return self._merge_story_bible_into_config(self._load_normalized_config())

    def get_workspace_settings(self) -> dict:
        story_bible_fields = self._get_story_bible_prompt_fields()
        state_snapshot = self._get_state_snapshot()
        return {
            "worldview": story_bible_fields.get("worldview", DEFAULT_CONFIG["worldview"]),
            "tone_and_manner": story_bible_fields.get("tone_and_manner", DEFAULT_CONFIG["tone_and_manner"]),
            "continuity": story_bible_fields.get("continuity", DEFAULT_CONFIG["continuity"]),
            "state": state_snapshot.get("state", DEFAULT_CONTEXT_STATE["state"]),
            "summary_of_previous": state_snapshot.get(
                "summary_of_previous",
                DEFAULT_CONTEXT_STATE["summary_of_previous"],
            ),
        }

    def get_characters(self) -> list[dict]:
        return self._normalize_characters(self._load_json(self.chars_path))

    def save_config(self, config_data: dict) -> None:
        normalized = self._normalize_config(config_data)
        legacy_config = self._load_normalized_config()
        legacy_config["worldview"] = normalized.get("worldview", DEFAULT_CONFIG["worldview"])
        legacy_config["tone_and_manner"] = normalized.get("tone_and_manner", DEFAULT_CONFIG["tone_and_manner"])
        legacy_config["continuity"] = normalized.get("continuity", DEFAULT_CONFIG["continuity"])
        self._write_legacy_config(legacy_config)
        self.story_bible_store.save(
            {
                "worldview": normalized.get("worldview", DEFAULT_CONFIG["worldview"]),
                "style_guide": normalized.get("tone_and_manner", DEFAULT_CONFIG["tone_and_manner"]),
                "fixed_rules": normalized.get("continuity", DEFAULT_CONFIG["continuity"]),
            }
        )

    def save_story_bible_sections(
        self,
        *,
        worldview: str,
        tone_and_manner: str,
        continuity: str,
    ) -> None:
        story_bible = self.story_bible_store.load()
        story_bible["worldview"] = str(worldview)
        story_bible["style_guide"] = str(tone_and_manner)
        story_bible["fixed_rules"] = str(continuity)
        self.story_bible_store.save(story_bible)

        config = self._load_normalized_config()
        config["worldview"] = str(worldview)
        config["tone_and_manner"] = str(tone_and_manner)
        config["continuity"] = str(continuity)
        self._write_legacy_config(config)

    def save_state(self, state: str) -> None:
        snapshot = self._get_state_snapshot()
        snapshot["state"] = str(state)
        self.context_state_store.save(snapshot)
        self._write_legacy_state_shadow(state=snapshot["state"])

    def save_previous_summary(self, summary_of_previous: str) -> None:
        snapshot = self._get_state_snapshot()
        snapshot["summary_of_previous"] = str(summary_of_previous)
        self.context_state_store.save(snapshot)
        self._write_legacy_state_shadow(summary_of_previous=snapshot["summary_of_previous"])

    def save_characters(self, chars_data: list) -> None:
        if not isinstance(chars_data, list):
            raise ValueError("등장인물 데이터는 JSON 배열(list)이어야 합니다.")

        normalized_chars = self._normalize_characters(chars_data)
        if len(normalized_chars) != len(chars_data):
            raise ValueError("등장인물 데이터에 잘못된 항목이 있습니다. id/name/role/description/traits가 필요합니다.")

        atomic_write_json(self.chars_path, normalized_chars)

    def build_updated_summary_text(self, new_summary: str, generator_instance=None) -> str:
        old_summary = self._get_state_snapshot().get("summary_of_previous", "").strip()
        if old_summary:
            updated_summary = old_summary + "\n\n[진행된 줄거리 요약]\n" + new_summary
        else:
            updated_summary = new_summary

        if generator_instance and len(updated_summary) > 3000:
            compressed = generator_instance.compress_history_summary(updated_summary)
            if compressed:
                updated_summary = compressed
        return updated_summary

    def update_summary(self, new_summary: str, generator_instance=None) -> None:
        updated_summary = self.build_updated_summary_text(new_summary, generator_instance=generator_instance)
        self.save_previous_summary(updated_summary)

    def apply_context_updates(
        self,
        *,
        state: str | None = None,
        summary_of_previous: str | None = None,
    ) -> dict:
        workspace_settings = self.get_workspace_settings()
        backup = {
            "state": workspace_settings.get("state", ""),
            "summary_of_previous": workspace_settings.get("summary_of_previous", ""),
        }
        applied = {
            "state": False,
            "summary_of_previous": False,
        }
        current_state = backup["state"]
        current_summary = backup["summary_of_previous"]

        if state is not None and str(state).strip():
            current_state = str(state)
            self.save_state(current_state)
            applied["state"] = True

        if summary_of_previous is not None and str(summary_of_previous).strip():
            current_summary = str(summary_of_previous)
            self.save_previous_summary(current_summary)
            applied["summary_of_previous"] = True

        return {
            "backup": backup,
            "applied": applied,
            "current": {
                "state": current_state,
                "summary_of_previous": current_summary,
            },
        }

    def update_worldview(self, new_worldview: str) -> None:
        workspace_settings = self.get_workspace_settings()
        self.save_story_bible_sections(
            worldview=str(new_worldview),
            tone_and_manner=workspace_settings.get("tone_and_manner", DEFAULT_CONFIG["tone_and_manner"]),
            continuity=workspace_settings.get("continuity", DEFAULT_CONFIG["continuity"]),
        )

    def get_plot_outline(self) -> str:
        return str(self._load_plot_payload().get("plot_outline", "")).strip()

    def save_plot_outline(self, plot_text: str) -> None:
        if not self.plot_store.plot_path.exists():
            self.plot_store.save(self._load_plot_payload())

        payload = self.plot_store.bump_version(plot_text)
        self._write_legacy_plot_shadow(payload)

    def build_plot_block(
        self,
        *,
        include_plot: bool = False,
        plot_strength: str = "balanced",
    ) -> str:
        plot_ctx = self.get_plot_outline()
        if not include_plot or not plot_ctx:
            return ""

        return f"""
[PLOT OUTLINE] (?κ린 ?뚮’ 媛?대뱶)
{plot_ctx}

[?뚮’ 諛섏쁺 媛뺣룄]
{plot_strength}
"""

    def build_generation_prompt(
        self,
        user_instruction: str,
        length_goal: int = 5000,
        include_plot: bool = False,
        plot_strength: str = "balanced",
    ) -> str:
        world_ctx = self.get_worldview_context()
        char_ctx = self.get_character_context()
        continuity_ctx = self.get_continuity_context()
        canon_ctx = self.get_canon_context()
        release_policy_ctx = self.get_release_policy_context()
        state_ctx = self.get_state_context()
        plot_block = self.build_plot_block(include_plot=include_plot, plot_strength=plot_strength)
        if False:
            plot_block = f"""
[PLOT OUTLINE] (장기 플롯 가이드)
{plot_ctx}

[플롯 반영 강도]
{plot_strength}
"""

        return f"""당신은 프로 웹소설 작가입니다. 다음 설정과 등장인물 정보를 바탕으로 다음 회차 본문을 작성해 주세요.
CONTINUITY를 깨지 말고, STATE의 갈등과 감정선을 자연스럽게 이어 주세요.

{world_ctx}
{continuity_ctx}
{canon_ctx}
{release_policy_ctx}
{state_ctx}
{char_ctx}
{plot_block}

[이번 회차 작성 지시사항]
{user_instruction}

[분량 및 서술 조건]
- 목표 분량: 공백 포함 약 {length_goal}자
- 제목은 생략하고 본문만 출력
"""
