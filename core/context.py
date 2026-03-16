import json
from pathlib import Path

from core.app_paths import DATA_PROJECTS_DIR
from core.canon_store import CanonStore
from core.context_characters import normalize_characters
from core.context_prompt_sections import (
    build_canon_context,
    build_character_context,
    build_continuity_context,
    build_generation_prompt as build_prompt_text,
    build_plot_block as build_plot_text,
    build_release_policy_context,
    build_state_context,
    build_worldview_context,
)
from core.context_state_shadow import load_state_shadow_snapshot, write_legacy_state_shadow
from core.context_state_store import DEFAULT_CONTEXT_STATE, ContextStateStore
from core.context_story_bible_shadow import (
    DEFAULT_STORY_BIBLE_SHADOW,
    load_raw_config_payload,
    load_story_bible_shadow_payload,
    normalize_story_bible_shadow_payload,
    write_story_bible_shadow,
    write_story_bible_shadow_payload,
)
from core.file_utils import atomic_write_json
from core.plot_store import DEFAULT_PLOT, PlotStore
from core.release_policy_store import ReleasePolicyStore
from core.story_bible_store import DEFAULT_STORY_BIBLE, StoryBibleStore


BASE_DATA_DIR = DATA_PROJECTS_DIR
# Primary public defaults for Story Bible-only settings.
DEFAULT_STORY_BIBLE_SETTINGS = DEFAULT_STORY_BIBLE_SHADOW


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
            atomic_write_json(self.config_path, DEFAULT_STORY_BIBLE_SHADOW.copy())
        if not self.chars_path.exists():
            self.save_characters([])

    def _default_value_for(self, path: Path) -> dict | list:
        if path.name == "config.json":
            return DEFAULT_STORY_BIBLE_SHADOW.copy()
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
            return DEFAULT_STORY_BIBLE_SHADOW.copy()

        if path.name != "config.json" and not isinstance(data, list):
            print(f"[ContextManager] Invalid characters shape at {path}: expected array")
            return []

        return data

    def _normalize_story_bible_shadow_payload(self, payload: dict | list) -> dict:
        merged = DEFAULT_STORY_BIBLE_SHADOW.copy()
        if not isinstance(payload, dict):
            return merged

        for key, default_value in DEFAULT_STORY_BIBLE_SHADOW.items():
            value = payload.get(key, default_value)
            if value is None:
                merged[key] = default_value
            else:
                merged[key] = value if isinstance(value, str) else str(value)
        return merged

    def _load_story_bible_shadow_payload(self) -> dict:
        return load_story_bible_shadow_payload(self.config_path)

    def _load_raw_config_payload(self) -> dict:
        return load_raw_config_payload(self.config_path)

    def _build_story_bible_compatibility_view(self, shadow_payload: dict) -> dict:
        merged = DEFAULT_STORY_BIBLE_SHADOW.copy()
        merged.update(shadow_payload)
        if not self.story_bible_store.story_bible_path.exists():
            return merged

        story_bible = self.story_bible_store.load()

        if (
            story_bible.get("worldview") != DEFAULT_STORY_BIBLE["worldview"]
            or merged["worldview"] == DEFAULT_STORY_BIBLE_SHADOW["worldview"]
        ):
            merged["worldview"] = story_bible.get("worldview", merged["worldview"])
        if (
            story_bible.get("style_guide") != DEFAULT_STORY_BIBLE["style_guide"]
            or merged["tone_and_manner"] == DEFAULT_STORY_BIBLE_SHADOW["tone_and_manner"]
        ):
            merged["tone_and_manner"] = story_bible.get("style_guide", merged["tone_and_manner"])
        if (
            story_bible.get("fixed_rules") != DEFAULT_STORY_BIBLE["fixed_rules"]
            or merged["continuity"] == DEFAULT_STORY_BIBLE_SHADOW["continuity"]
        ):
            merged["continuity"] = story_bible.get("fixed_rules", merged["continuity"])

        return merged

    def _write_story_bible_shadow_payload(self, payload: dict) -> None:
        write_story_bible_shadow_payload(self.config_path, payload)

    def _write_story_bible_shadow(
        self,
        *,
        worldview: str,
        tone_and_manner: str,
        continuity: str,
    ) -> None:
        write_story_bible_shadow(
            self.config_path,
            worldview=worldview,
            tone_and_manner=tone_and_manner,
            continuity=continuity,
        )

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
            config = DEFAULT_STORY_BIBLE_SHADOW.copy()
        config["plot_outline"] = str(payload.get("plot_outline", ""))
        config["plot_version"] = str(payload.get("plot_version", "0"))
        atomic_write_json(self.config_path, config)

    def _write_legacy_state_shadow(
        self,
        *,
        state: str | None = None,
        summary_of_previous: str | None = None,
    ) -> None:
        write_legacy_state_shadow(
            self.config_path,
            state=state,
            summary_of_previous=summary_of_previous,
        )

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
        return load_state_shadow_snapshot(self.config_path)

    def get_worldview_context(self) -> str:
        prompt_fields = self._get_story_bible_prompt_fields()
        worldview = prompt_fields.get("worldview", "")
        tone = prompt_fields.get("tone_and_manner", "")
        return build_worldview_context(worldview, tone)

    def get_continuity_context(self) -> str:
        continuity = self._get_story_bible_prompt_fields().get("continuity", "")
        return build_continuity_context(continuity)

    def get_canon_context(self) -> str:
        canon_state = self.canon_store.load_current_state()
        return build_canon_context(canon_state)

    def get_release_policy_context(self) -> str:
        release_policy = self.release_policy_store.load()
        return build_release_policy_context(release_policy)

    def get_state_context(self) -> str:
        state_snapshot = self._get_state_snapshot()
        state_info = state_snapshot.get("state", "")
        prev_summary = state_snapshot.get("summary_of_previous", "")
        return build_state_context(state_info, prev_summary)

    def get_character_context(self) -> str:
        return build_character_context(self.get_characters())

    def get_story_bible_settings(self) -> dict:
        """primary Story Bible settings read API."""
        return self._build_story_bible_compatibility_view(self._load_story_bible_shadow_payload())

    def get_workspace_settings(self) -> dict:
        story_bible_fields = self._get_story_bible_prompt_fields()
        state_snapshot = self._get_state_snapshot()
        return {
            "worldview": story_bible_fields.get("worldview", DEFAULT_STORY_BIBLE_SETTINGS["worldview"]),
            "tone_and_manner": story_bible_fields.get(
                "tone_and_manner",
                DEFAULT_STORY_BIBLE_SETTINGS["tone_and_manner"],
            ),
            "continuity": story_bible_fields.get("continuity", DEFAULT_STORY_BIBLE_SETTINGS["continuity"]),
            "state": state_snapshot.get("state", DEFAULT_CONTEXT_STATE["state"]),
            "summary_of_previous": state_snapshot.get(
                "summary_of_previous",
                DEFAULT_CONTEXT_STATE["summary_of_previous"],
            ),
        }

    def get_characters(self) -> list[dict]:
        return normalize_characters(self._load_json(self.chars_path))

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
        self._write_story_bible_shadow(
            worldview=str(worldview),
            tone_and_manner=str(tone_and_manner),
            continuity=str(continuity),
        )

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

        normalized_chars = normalize_characters(chars_data)
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
            tone_and_manner=workspace_settings.get(
                "tone_and_manner",
                DEFAULT_STORY_BIBLE_SETTINGS["tone_and_manner"],
            ),
            continuity=workspace_settings.get("continuity", DEFAULT_STORY_BIBLE_SETTINGS["continuity"]),
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
        return build_plot_text(
            plot_outline=self.get_plot_outline(),
            include_plot=include_plot,
            plot_strength=plot_strength,
        )

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
        return build_prompt_text(
            worldview_context=world_ctx,
            continuity_context=continuity_ctx,
            canon_context=canon_ctx,
            release_policy_context=release_policy_ctx,
            state_context=state_ctx,
            character_context=char_ctx,
            plot_block=plot_block,
            user_instruction=user_instruction,
            length_goal=length_goal,
        )
