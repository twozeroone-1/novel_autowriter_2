import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.canon_store as canon_store_module
import core.context as context_module
import core.context_state_store as context_state_store_module
import core.plot_store as plot_store_module
import core.release_policy_store as release_policy_store_module
import core.story_bible_store as story_bible_store_module
from core.canon_store import CanonStore
from core.context import ContextManager
from core.context_state_store import ContextStateStore
from core.plot_store import PlotStore
from core.release_policy_store import ReleasePolicyStore
from core.story_bible_store import StoryBibleStore


class TestContextManager(unittest.TestCase):
    def _patch_all_project_dirs(self, tmpdir: str):
        base = Path(tmpdir)
        return patch.multiple(
            context_module,
            BASE_DATA_DIR=base,
        )

    def test_get_story_bible_settings_normalize_missing_and_non_string_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.config_path.write_text('{"worldview": 123, "state": null}', encoding="utf-8")

                settings = manager.get_story_bible_settings()
                workspace_settings = manager.get_workspace_settings()

                self.assertEqual(settings["worldview"], "123")
                self.assertEqual(
                    settings["tone_and_manner"],
                    context_module.DEFAULT_STORY_BIBLE_SETTINGS["tone_and_manner"],
                )
                self.assertNotIn("state", settings)
                self.assertNotIn("summary_of_previous", settings)
                self.assertEqual(workspace_settings["state"], context_state_store_module.DEFAULT_CONTEXT_STATE["state"])
                self.assertEqual(
                    workspace_settings["summary_of_previous"],
                    context_state_store_module.DEFAULT_CONTEXT_STATE["summary_of_previous"],
                )

    def test_get_characters_skips_invalid_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")
                manager.chars_path.write_text(
                    """
[
  {"id": "char_001", "name": "Lead", "role": "Lead", "description": "desc", "traits": ["calm"]},
  {"id": "char_002", "name": "Support"}
]
""".strip(),
                    encoding="utf-8",
                )

                characters = manager.get_characters()

                self.assertEqual(len(characters), 1)
                self.assertEqual(characters[0]["id"], "char_001")

    def test_update_summary_appends_new_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")
                manager.save_previous_summary("existing summary")

                manager.update_summary("new summary")

                updated = manager.get_workspace_settings()["summary_of_previous"]
                self.assertIn("existing summary", updated)
                self.assertIn("new summary", updated)
                self.assertIn("[진행된 줄거리 요약]", updated)

    def test_update_summary_uses_compression_when_too_long(self):
        class FakeGenerator:
            def __init__(self):
                self.calls = []

            def compress_history_summary(self, summary: str) -> str:
                self.calls.append(summary)
                return "compressed summary"

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")
                manager.save_previous_summary("a" * 2995)
                fake_generator = FakeGenerator()

                manager.update_summary("b" * 20, generator_instance=fake_generator)

                self.assertEqual(len(fake_generator.calls), 1)
                self.assertEqual(manager.get_workspace_settings()["summary_of_previous"], "compressed summary")

    def test_update_summary_uses_dedicated_summary_save_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")
                manager.save_previous_summary("existing summary")
                expected_summary = manager.build_updated_summary_text("new summary")

                with patch.object(manager, "save_previous_summary") as save_previous_summary, patch.object(
                    manager, "save_config"
                ) as save_config:
                    manager.update_summary("new summary")

                save_previous_summary.assert_called_once_with(expected_summary)
                save_config.assert_not_called()

    def test_build_updated_summary_text_returns_combined_preview_without_saving(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")
                manager.save_previous_summary("existing summary")

                preview = manager.build_updated_summary_text("new summary")

                self.assertIn("existing summary", preview)
                self.assertIn("new summary", preview)
                self.assertEqual(manager.get_workspace_settings()["summary_of_previous"], "existing summary")

    def test_apply_context_updates_returns_backup_and_persists_new_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")
                manager.save_state("old state")
                manager.save_previous_summary("old summary")

                result = manager.apply_context_updates(
                    state="new state",
                    summary_of_previous="new summary",
                )

                workspace_settings = manager.get_workspace_settings()
                self.assertEqual(result["backup"]["state"], "old state")
                self.assertEqual(result["backup"]["summary_of_previous"], "old summary")
                self.assertTrue(result["applied"]["state"])
                self.assertTrue(result["applied"]["summary_of_previous"])
                self.assertEqual(workspace_settings["state"], "new state")
                self.assertEqual(workspace_settings["summary_of_previous"], "new summary")

    def test_apply_context_updates_only_persists_non_empty_overrides(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")
                manager.save_state("old state")
                manager.save_previous_summary("old summary")

                with patch.object(manager, "save_state", wraps=manager.save_state) as save_state, patch.object(
                    manager,
                    "save_previous_summary",
                    wraps=manager.save_previous_summary,
                ) as save_previous_summary, patch.object(
                    manager,
                    "save_config",
                    side_effect=AssertionError("save_config should not be used"),
                ):
                    result = manager.apply_context_updates(
                        state="   ",
                        summary_of_previous="new summary",
                    )

                workspace_settings = manager.get_workspace_settings()
                save_state.assert_not_called()
                save_previous_summary.assert_called_once_with("new summary")
                self.assertEqual(result["backup"]["state"], "old state")
                self.assertEqual(result["backup"]["summary_of_previous"], "old summary")
                self.assertFalse(result["applied"]["state"])
                self.assertTrue(result["applied"]["summary_of_previous"])
                self.assertEqual(result["current"]["state"], "old state")
                self.assertEqual(result["current"]["summary_of_previous"], "new summary")
                self.assertEqual(workspace_settings["state"], "old state")
                self.assertEqual(workspace_settings["summary_of_previous"], "new summary")

    # Primary Story Bible path

    def test_get_story_bible_settings_read_story_bible_fields_from_structured_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                store = StoryBibleStore(project_name="sample")
                store.save(
                    {
                        "worldview": "structured world",
                        "style_guide": "structured style",
                        "fixed_rules": "structured rules",
                        "author_intent": "keep tension",
                    }
                )
                manager = ContextManager(project_name="sample")

                settings = manager.get_story_bible_settings()

                self.assertEqual(settings["worldview"], "structured world")
                self.assertEqual(settings["tone_and_manner"], "structured style")
                self.assertEqual(settings["continuity"], "structured rules")

    def test_context_module_no_longer_exports_default_config_alias(self):
        self.assertFalse(hasattr(context_module, "DEFAULT_CONFIG"))

    def test_context_manager_no_longer_exposes_get_config_alias(self):
        self.assertFalse(hasattr(ContextManager, "get_config"))

    def test_context_manager_no_longer_exposes_save_config_alias(self):
        self.assertFalse(hasattr(ContextManager, "save_config"))

    # Compatibility alias path

    def test_default_config_compatibility_alias_points_to_story_bible_defaults(self):
        self.assertIs(context_module.DEFAULT_CONFIG, context_module.DEFAULT_STORY_BIBLE_SETTINGS)

    def test_get_story_bible_settings_docstring_marks_primary_api(self):
        self.assertIn("primary", ContextManager.get_story_bible_settings.__doc__ or "")

    def test_get_config_docstring_marks_compatibility_alias(self):
        self.assertIn("compatibility", ContextManager.get_config.__doc__ or "")

    def test_save_config_docstring_marks_compatibility_alias(self):
        self.assertIn("compatibility", ContextManager.save_config.__doc__ or "")

    def test_get_story_bible_settings_returns_story_bible_compatibility_view(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.save_story_bible_sections(
                    worldview="structured world",
                    tone_and_manner="structured style",
                    continuity="structured rules",
                )

                settings = manager.get_story_bible_settings()

                self.assertEqual(
                    settings,
                    {
                        "worldview": "structured world",
                        "tone_and_manner": "structured style",
                        "continuity": "structured rules",
                    },
                )

    def test_get_config_compatibility_alias_matches_story_bible_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.save_story_bible_sections(
                    worldview="structured world",
                    tone_and_manner="structured style",
                    continuity="structured rules",
                )

                self.assertEqual(manager.get_config(), manager.get_story_bible_settings())

    def test_get_story_bible_settings_do_not_expose_state_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                context_state_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.save_state("stored state")
                manager.save_previous_summary("stored summary")

                settings = manager.get_story_bible_settings()

                self.assertNotIn("state", settings)
                self.assertNotIn("summary_of_previous", settings)

    def test_get_workspace_settings_includes_state_fields_from_context_state_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                context_state_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                ContextStateStore(project_name="sample").save(
                    {
                        "state": "stored state",
                        "summary_of_previous": "stored summary",
                    }
                )

                workspace_settings = manager.get_workspace_settings()

                self.assertEqual(workspace_settings["state"], "stored state")
                self.assertEqual(workspace_settings["summary_of_previous"], "stored summary")

    def test_get_worldview_context_reads_story_bible_without_get_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.save_story_bible_sections(
                    worldview="structured world",
                    tone_and_manner="structured style",
                    continuity="structured rules",
                )

                with patch.object(manager, "get_config", side_effect=AssertionError("get_config should not be used")):
                    context_text = manager.get_worldview_context()

                self.assertIn("structured world", context_text)
                self.assertIn("structured style", context_text)

    def test_get_continuity_context_reads_story_bible_without_get_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.save_story_bible_sections(
                    worldview="structured world",
                    tone_and_manner="structured style",
                    continuity="structured rules",
                )

                with patch.object(manager, "get_config", side_effect=AssertionError("get_config should not be used")):
                    context_text = manager.get_continuity_context()

                self.assertIn("structured rules", context_text)

    def test_get_state_context_reads_state_snapshot_without_get_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")
                manager.save_state("current state")
                manager.save_previous_summary("previous summary")

                with patch.object(manager, "get_config", side_effect=AssertionError("get_config should not be used")):
                    context_text = manager.get_state_context()

                self.assertIn("current state", context_text)
                self.assertIn("previous summary", context_text)

    def test_build_updated_summary_text_reads_existing_summary_without_get_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")
                manager.save_previous_summary("existing summary")

                with patch.object(manager, "get_config", side_effect=AssertionError("get_config should not be used")):
                    preview = manager.build_updated_summary_text("new summary")

                self.assertIn("existing summary", preview)
                self.assertIn("new summary", preview)

    def test_save_state_updates_state_store_and_legacy_shadow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                context_state_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")

                manager.save_state("new state")

                store = ContextStateStore(project_name="sample")
                legacy_config = json.loads(manager.config_path.read_text(encoding="utf-8"))
                self.assertEqual(store.load()["state"], "new state")
                self.assertEqual(legacy_config["state"], "new state")

    def test_save_previous_summary_updates_state_store_and_legacy_shadow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                context_state_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")

                manager.save_previous_summary("new summary")

                store = ContextStateStore(project_name="sample")
                legacy_config = json.loads(manager.config_path.read_text(encoding="utf-8"))
                self.assertEqual(store.load()["summary_of_previous"], "new summary")
                self.assertEqual(legacy_config["summary_of_previous"], "new summary")

    def test_get_workspace_settings_prefers_context_state_store_over_legacy_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                context_state_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.config_path.write_text(
                    json.dumps(
                        {
                            **context_module.DEFAULT_STORY_BIBLE_SETTINGS,
                            "state": "legacy state",
                            "summary_of_previous": "legacy summary",
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                ContextStateStore(project_name="sample").save(
                    {
                        "state": "stored state",
                        "summary_of_previous": "stored summary",
                    }
                )

                workspace_settings = manager.get_workspace_settings()

                self.assertEqual(workspace_settings["state"], "stored state")
                self.assertEqual(workspace_settings["summary_of_previous"], "stored summary")

    def test_get_workspace_settings_falls_back_to_legacy_state_when_state_store_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                context_state_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.config_path.write_text(
                    json.dumps(
                        {
                            **context_module.DEFAULT_STORY_BIBLE_SETTINGS,
                            "state": "legacy state",
                            "summary_of_previous": "legacy summary",
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                workspace_settings = manager.get_workspace_settings()

                self.assertEqual(workspace_settings["state"], "legacy state")
                self.assertEqual(workspace_settings["summary_of_previous"], "legacy summary")

    # Compatibility alias write path

    def test_save_config_compatibility_alias_updates_story_bible_store_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")

                manager.save_config(
                    {
                        **context_module.DEFAULT_CONFIG,
                        "worldview": "new world",
                        "tone_and_manner": "new style",
                        "continuity": "new rules",
                    }
                )

                story_bible = StoryBibleStore(project_name="sample").load()

                self.assertEqual(story_bible["worldview"], "new world")
                self.assertEqual(story_bible["style_guide"], "new style")
                self.assertEqual(story_bible["fixed_rules"], "new rules")

    def test_get_workspace_settings_reads_story_bible_and_legacy_state_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.config_path.write_text(
                    json.dumps(
                        {
                            **context_module.DEFAULT_STORY_BIBLE_SETTINGS,
                            "worldview": "legacy world",
                            "tone_and_manner": "legacy style",
                            "continuity": "legacy rules",
                            "state": "legacy state",
                            "summary_of_previous": "legacy summary",
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                StoryBibleStore(project_name="sample").save(
                    {
                        "worldview": "structured world",
                        "style_guide": "structured style",
                        "fixed_rules": "structured rules",
                        "author_intent": "keep pressure high",
                    }
                )

                workspace_settings = manager.get_workspace_settings()

                self.assertEqual(workspace_settings["worldview"], "structured world")
                self.assertEqual(workspace_settings["tone_and_manner"], "structured style")
                self.assertEqual(workspace_settings["continuity"], "structured rules")
                self.assertEqual(workspace_settings["state"], "legacy state")
                self.assertEqual(workspace_settings["summary_of_previous"], "legacy summary")

    def test_get_story_bible_settings_do_not_expose_plot_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                plot_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.save_plot_outline("stored plot")

                settings = manager.get_story_bible_settings()

                self.assertNotIn("plot_outline", settings)
                self.assertNotIn("plot_version", settings)

    def test_save_story_bible_sections_updates_story_bible_store_and_legacy_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")

                manager.save_story_bible_sections(
                    worldview="new world",
                    tone_and_manner="new style",
                    continuity="new rules",
                )

                story_bible = StoryBibleStore(project_name="sample").load()
                settings = manager.get_story_bible_settings()

                self.assertEqual(story_bible["worldview"], "new world")
                self.assertEqual(story_bible["style_guide"], "new style")
                self.assertEqual(story_bible["fixed_rules"], "new rules")
                self.assertEqual(settings["worldview"], "new world")
                self.assertEqual(settings["tone_and_manner"], "new style")
                self.assertEqual(settings["continuity"], "new rules")

    def test_new_project_config_initializes_story_bible_shadow_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")

                config_payload = json.loads(manager.config_path.read_text(encoding="utf-8"))

                self.assertEqual(config_payload, context_module.DEFAULT_STORY_BIBLE_SETTINGS)
                self.assertNotIn("state", config_payload)
                self.assertNotIn("summary_of_previous", config_payload)
                self.assertNotIn("plot_outline", config_payload)
                self.assertNotIn("plot_version", config_payload)

    def test_save_story_bible_sections_routes_story_bible_shadow_write_through_shared_helper(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")

                with patch.object(
                    manager,
                    "_write_story_bible_shadow",
                    wraps=manager._write_story_bible_shadow,
                ) as write_story_bible_shadow:
                    manager.save_story_bible_sections(
                        worldview="new world",
                        tone_and_manner="new style",
                        continuity="new rules",
                    )

                write_story_bible_shadow.assert_called_once_with(
                    worldview="new world",
                    tone_and_manner="new style",
                    continuity="new rules",
                )
                story_bible = StoryBibleStore(project_name="sample").load()
                self.assertEqual(story_bible["worldview"], "new world")
                self.assertEqual(story_bible["style_guide"], "new style")
                self.assertEqual(story_bible["fixed_rules"], "new rules")

    def test_save_story_bible_sections_preserves_existing_state_and_plot_shadow_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.config_path.write_text(
                    json.dumps(
                        {
                            **context_module.DEFAULT_STORY_BIBLE_SETTINGS,
                            "state": "legacy state",
                            "summary_of_previous": "legacy summary",
                            "plot_outline": "legacy plot",
                            "plot_version": "4",
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                manager.save_story_bible_sections(
                    worldview="new world",
                    tone_and_manner="new style",
                    continuity="new rules",
                )

                config_payload = json.loads(manager.config_path.read_text(encoding="utf-8"))
                self.assertEqual(config_payload["worldview"], "new world")
                self.assertEqual(config_payload["tone_and_manner"], "new style")
                self.assertEqual(config_payload["continuity"], "new rules")
                self.assertEqual(config_payload["state"], "legacy state")
                self.assertEqual(config_payload["summary_of_previous"], "legacy summary")
                self.assertEqual(config_payload["plot_outline"], "legacy plot")
                self.assertEqual(config_payload["plot_version"], "4")

    def test_update_worldview_uses_story_bible_save_path_and_preserves_other_sections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.save_story_bible_sections(
                    worldview="old world",
                    tone_and_manner="existing style",
                    continuity="existing rules",
                )

                with patch.object(
                    manager,
                    "save_story_bible_sections",
                    wraps=manager.save_story_bible_sections,
                ) as save_story_bible_sections, patch.object(
                    manager,
                    "save_config",
                    side_effect=AssertionError("save_config should not be used"),
                ):
                    manager.update_worldview("new world")

                save_story_bible_sections.assert_called_once_with(
                    worldview="new world",
                    tone_and_manner="existing style",
                    continuity="existing rules",
                )
                story_bible = StoryBibleStore(project_name="sample").load()
                settings = manager.get_story_bible_settings()
                self.assertEqual(story_bible["worldview"], "new world")
                self.assertEqual(story_bible["style_guide"], "existing style")
                self.assertEqual(story_bible["fixed_rules"], "existing rules")
                self.assertEqual(settings["worldview"], "new world")
                self.assertEqual(settings["tone_and_manner"], "existing style")
                self.assertEqual(settings["continuity"], "existing rules")

    def test_get_plot_outline_prefers_plot_store_over_legacy_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                plot_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.config_path.write_text(
                    json.dumps(
                        {
                            **context_module.DEFAULT_STORY_BIBLE_SETTINGS,
                            "plot_outline": "legacy plot",
                            "plot_version": "2",
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                PlotStore(project_name="sample").save(
                    {
                        "plot_outline": "stored plot",
                        "plot_version": "7",
                    }
                )

                plot_outline = manager.get_plot_outline()

                self.assertEqual(plot_outline, "stored plot")

    def test_get_plot_outline_falls_back_to_raw_legacy_plot_fields_when_plot_store_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                plot_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.config_path.write_text(
                    json.dumps(
                        {
                            **context_module.DEFAULT_STORY_BIBLE_SETTINGS,
                            "plot_outline": "legacy plot",
                            "plot_version": "2",
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                plot_outline = manager.get_plot_outline()

                self.assertEqual(plot_outline, "legacy plot")

    def test_save_config_compatibility_alias_ignores_plot_fields_and_keeps_existing_plot_store_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                plot_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ), patch.object(story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")
                manager.save_plot_outline("stored plot")

                manager.save_config(
                    {
                        **context_module.DEFAULT_CONFIG,
                        "worldview": "new world",
                        "tone_and_manner": "new style",
                        "continuity": "new rules",
                        "plot_outline": "ignored plot",
                        "plot_version": "99",
                    }
                )

                settings = manager.get_story_bible_settings()
                plot_payload = PlotStore(project_name="sample").load()

                self.assertEqual(settings["worldview"], "new world")
                self.assertNotIn("plot_outline", settings)
                self.assertNotIn("plot_version", settings)
                self.assertEqual(plot_payload["plot_outline"], "stored plot")
                self.assertEqual(plot_payload["plot_version"], "1")

    def test_save_config_compatibility_alias_routes_story_bible_shadow_write_through_shared_helper(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")

                with patch.object(
                    manager,
                    "_write_story_bible_shadow",
                    wraps=manager._write_story_bible_shadow,
                ) as write_story_bible_shadow:
                    manager.save_config(
                        {
                            **context_module.DEFAULT_CONFIG,
                            "worldview": "new world",
                            "tone_and_manner": "new style",
                            "continuity": "new rules",
                        }
                    )

                write_story_bible_shadow.assert_called_once_with(
                    worldview="new world",
                    tone_and_manner="new style",
                    continuity="new rules",
                )
                story_bible = StoryBibleStore(project_name="sample").load()
                self.assertEqual(story_bible["worldview"], "new world")
                self.assertEqual(story_bible["style_guide"], "new style")
                self.assertEqual(story_bible["fixed_rules"], "new rules")

    def test_save_config_compatibility_alias_delegates_to_save_story_bible_sections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")

                with patch.object(
                    manager,
                    "save_story_bible_sections",
                    wraps=manager.save_story_bible_sections,
                ) as save_story_bible_sections:
                    manager.save_config(
                        {
                            **context_module.DEFAULT_CONFIG,
                            "worldview": "new world",
                            "tone_and_manner": "new style",
                            "continuity": "new rules",
                        }
                    )

                save_story_bible_sections.assert_called_once_with(
                    worldview="new world",
                    tone_and_manner="new style",
                    continuity="new rules",
                )

    def test_save_config_compatibility_alias_ignores_state_fields_and_preserves_existing_context_state_store_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ), patch.object(context_state_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")
                manager.save_state("stored state")
                manager.save_previous_summary("stored summary")

                manager.save_config(
                    {
                        **context_module.DEFAULT_CONFIG,
                        "worldview": "new world",
                        "tone_and_manner": "new style",
                        "continuity": "new rules",
                        "state": "ignored state",
                        "summary_of_previous": "ignored summary",
                    }
                )

                settings = manager.get_story_bible_settings()
                workspace_settings = manager.get_workspace_settings()
                state_payload = ContextStateStore(project_name="sample").load()
                legacy_config = json.loads(manager.config_path.read_text(encoding="utf-8"))

                self.assertEqual(settings["worldview"], "new world")
                self.assertNotIn("state", settings)
                self.assertNotIn("summary_of_previous", settings)
                self.assertEqual(workspace_settings["state"], "stored state")
                self.assertEqual(workspace_settings["summary_of_previous"], "stored summary")
                self.assertEqual(state_payload["state"], "stored state")
                self.assertEqual(state_payload["summary_of_previous"], "stored summary")
                self.assertEqual(legacy_config["state"], "stored state")
                self.assertEqual(legacy_config["summary_of_previous"], "stored summary")

    def test_save_config_compatibility_alias_does_not_create_context_state_store_from_state_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ), patch.object(context_state_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")

                manager.save_config(
                    {
                        **context_module.DEFAULT_CONFIG,
                        "worldview": "new world",
                        "tone_and_manner": "new style",
                        "continuity": "new rules",
                        "state": "ignored state",
                        "summary_of_previous": "ignored summary",
                    }
                )

                state_store = ContextStateStore(project_name="sample")
                legacy_config = json.loads(manager.config_path.read_text(encoding="utf-8"))

                self.assertFalse(state_store.context_state_path.exists())
                self.assertNotIn("state", legacy_config)
                self.assertNotIn("summary_of_previous", legacy_config)

    def test_save_plot_outline_updates_plot_store_and_legacy_shadow_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                plot_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.config_path.write_text(
                    json.dumps(
                        {
                            **context_module.DEFAULT_STORY_BIBLE_SETTINGS,
                            "plot_outline": "legacy plot",
                            "plot_version": "2",
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                with patch.object(manager, "save_config", side_effect=AssertionError("save_config should not be used")):
                    manager.save_plot_outline("new stored plot")

                plot_payload = PlotStore(project_name="sample").load()
                legacy_config = json.loads(manager.config_path.read_text(encoding="utf-8"))
                self.assertEqual(
                    plot_payload,
                    {
                        "plot_outline": "new stored plot",
                        "plot_version": "3",
                    },
                )
                self.assertEqual(legacy_config["plot_outline"], "new stored plot")
                self.assertEqual(legacy_config["plot_version"], "3")

    def test_save_state_and_previous_summary_update_only_target_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.save_story_bible_sections(
                    worldview="fixed world",
                    tone_and_manner="fixed style",
                    continuity="fixed rules",
                )

                manager.save_state("next confrontation is unavoidable")
                manager.save_previous_summary("the hero escaped with the contract")

                settings = manager.get_story_bible_settings()
                workspace_settings = manager.get_workspace_settings()
                story_bible = StoryBibleStore(project_name="sample").load()

                self.assertNotIn("state", settings)
                self.assertNotIn("summary_of_previous", settings)
                self.assertEqual(workspace_settings["state"], "next confrontation is unavoidable")
                self.assertEqual(workspace_settings["summary_of_previous"], "the hero escaped with the contract")
                self.assertEqual(story_bible["worldview"], "fixed world")
                self.assertEqual(story_bible["style_guide"], "fixed style")
                self.assertEqual(story_bible["fixed_rules"], "fixed rules")

    def test_build_generation_prompt_includes_all_context_and_plot_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ), patch.object(canon_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)), patch.object(
                release_policy_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.save_story_bible_sections(
                    worldview="world data",
                    tone_and_manner="tone guide",
                    continuity="fixed rules",
                )
                manager.save_state("current state")
                manager.save_previous_summary("previous summary")
                manager.save_plot_outline("plot outline text")
                CanonStore(project_name="sample").save_current_state(
                    {
                        "people": {"Hero": {"mood": "alert"}},
                        "resources": {"cash": 10},
                        "hooks": ["mystery"],
                        "timeline": ["ep_001"],
                    }
                )
                ReleasePolicyStore(project_name="sample").save(
                    {
                        "global": {"max_daily_releases": 2, "burst_allowed": True},
                        "platforms": {"munpia": {"enabled": True, "default_times": ["07:00"]}},
                    }
                )
                manager.save_characters(
                    [
                        {
                            "id": "char_001",
                            "name": "Hero",
                            "role": "Lead",
                            "description": "Main character",
                            "traits": ["calm", "smart"],
                        }
                    ]
                )

                prompt = manager.build_generation_prompt(
                    "write next chapter",
                    length_goal=4000,
                    include_plot=True,
                    plot_strength="strict",
                )

                self.assertIn("world data", prompt)
                self.assertIn("tone guide", prompt)
                self.assertIn("fixed rules", prompt)
                self.assertIn("current state", prompt)
                self.assertIn("previous summary", prompt)
                self.assertIn("Hero", prompt)
                self.assertIn("plot outline text", prompt)
                self.assertIn("strict", prompt)
                self.assertIn("[CANON FACTS]", prompt)
                self.assertIn("mystery", prompt)
                self.assertIn("[RELEASE POLICY]", prompt)
                self.assertIn("max_daily_releases", prompt)
                self.assertIn("write next chapter", prompt)
                self.assertIn("4000", prompt)

    def test_build_generation_prompt_omits_plot_block_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")
                manager.save_plot_outline("plot outline text")

                prompt = manager.build_generation_prompt(
                    "write next chapter",
                    include_plot=False,
                    plot_strength="strict",
                )

                self.assertNotIn("plot outline text", prompt)
                self.assertNotIn("[PLOT OUTLINE]", prompt)


if __name__ == "__main__":
    unittest.main()
