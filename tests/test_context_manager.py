import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.canon_store as canon_store_module
import core.context as context_module
import core.plot_store as plot_store_module
import core.release_policy_store as release_policy_store_module
import core.story_bible_store as story_bible_store_module
from core.canon_store import CanonStore
from core.context import ContextManager
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

    def test_get_config_normalizes_missing_and_non_string_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.config_path.write_text('{"worldview": 123, "state": null}', encoding="utf-8")

                config = manager.get_config()

                self.assertEqual(config["worldview"], "123")
                self.assertEqual(config["state"], context_module.DEFAULT_CONFIG["state"])
                self.assertEqual(config["tone_and_manner"], context_module.DEFAULT_CONFIG["tone_and_manner"])

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
                manager.save_config(
                    {
                        **context_module.DEFAULT_CONFIG,
                        "summary_of_previous": "existing summary",
                    }
                )

                manager.update_summary("new summary")

                updated = manager.get_config()["summary_of_previous"]
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
                manager.save_config(
                    {
                        **context_module.DEFAULT_CONFIG,
                        "summary_of_previous": "a" * 2995,
                    }
                )
                fake_generator = FakeGenerator()

                manager.update_summary("b" * 20, generator_instance=fake_generator)

                self.assertEqual(len(fake_generator.calls), 1)
                self.assertEqual(manager.get_config()["summary_of_previous"], "compressed summary")

    def test_update_summary_uses_dedicated_summary_save_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")
                manager.save_config(
                    {
                        **context_module.DEFAULT_CONFIG,
                        "summary_of_previous": "existing summary",
                    }
                )
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
                manager.save_config(
                    {
                        **context_module.DEFAULT_CONFIG,
                        "summary_of_previous": "existing summary",
                    }
                )

                preview = manager.build_updated_summary_text("new summary")

                self.assertIn("existing summary", preview)
                self.assertIn("new summary", preview)
                self.assertEqual(manager.get_config()["summary_of_previous"], "existing summary")

    def test_apply_context_updates_returns_backup_and_persists_new_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")
                manager.save_config(
                    {
                        **context_module.DEFAULT_CONFIG,
                        "state": "old state",
                        "summary_of_previous": "old summary",
                    }
                )

                result = manager.apply_context_updates(
                    state="new state",
                    summary_of_previous="new summary",
                )

                config = manager.get_config()
                self.assertEqual(result["backup"]["state"], "old state")
                self.assertEqual(result["backup"]["summary_of_previous"], "old summary")
                self.assertTrue(result["applied"]["state"])
                self.assertTrue(result["applied"]["summary_of_previous"])
                self.assertEqual(config["state"], "new state")
                self.assertEqual(config["summary_of_previous"], "new summary")

    def test_apply_context_updates_only_persists_non_empty_overrides(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                manager = ContextManager(project_name="sample")
                manager.save_config(
                    {
                        **context_module.DEFAULT_CONFIG,
                        "state": "old state",
                        "summary_of_previous": "old summary",
                    }
                )

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

                config = manager.get_config()
                save_state.assert_not_called()
                save_previous_summary.assert_called_once_with("new summary")
                self.assertEqual(result["backup"]["state"], "old state")
                self.assertEqual(result["backup"]["summary_of_previous"], "old summary")
                self.assertFalse(result["applied"]["state"])
                self.assertTrue(result["applied"]["summary_of_previous"])
                self.assertEqual(result["current"]["state"], "old state")
                self.assertEqual(result["current"]["summary_of_previous"], "new summary")
                self.assertEqual(config["state"], "old state")
                self.assertEqual(config["summary_of_previous"], "new summary")

    def test_get_config_reads_story_bible_fields_from_structured_store(self):
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

                config = manager.get_config()

                self.assertEqual(config["worldview"], "structured world")
                self.assertEqual(config["tone_and_manner"], "structured style")
                self.assertEqual(config["continuity"], "structured rules")

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

    def test_save_config_updates_story_bible_store_fields(self):
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
                manager.save_config(
                    {
                        **context_module.DEFAULT_CONFIG,
                        "worldview": "legacy world",
                        "tone_and_manner": "legacy style",
                        "continuity": "legacy rules",
                        "state": "legacy state",
                        "summary_of_previous": "legacy summary",
                    }
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

    def test_get_config_does_not_expose_plot_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                plot_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.save_plot_outline("stored plot")

                config = manager.get_config()

                self.assertNotIn("plot_outline", config)
                self.assertNotIn("plot_version", config)

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
                config = manager.get_config()

                self.assertEqual(story_bible["worldview"], "new world")
                self.assertEqual(story_bible["style_guide"], "new style")
                self.assertEqual(story_bible["fixed_rules"], "new rules")
                self.assertEqual(config["worldview"], "new world")
                self.assertEqual(config["tone_and_manner"], "new style")
                self.assertEqual(config["continuity"], "new rules")

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
                config = manager.get_config()
                self.assertEqual(story_bible["worldview"], "new world")
                self.assertEqual(story_bible["style_guide"], "existing style")
                self.assertEqual(story_bible["fixed_rules"], "existing rules")
                self.assertEqual(config["worldview"], "new world")
                self.assertEqual(config["tone_and_manner"], "existing style")
                self.assertEqual(config["continuity"], "existing rules")

    def test_get_plot_outline_prefers_plot_store_over_legacy_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                plot_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.config_path.write_text(
                    json.dumps(
                        {
                            **context_module.DEFAULT_CONFIG,
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
                            **context_module.DEFAULT_CONFIG,
                            "plot_outline": "legacy plot",
                            "plot_version": "2",
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                plot_outline = manager.get_plot_outline()

                self.assertEqual(plot_outline, "legacy plot")

    def test_save_config_ignores_plot_fields_and_keeps_existing_plot_store_value(self):
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

                config = manager.get_config()
                plot_payload = PlotStore(project_name="sample").load()

                self.assertEqual(config["worldview"], "new world")
                self.assertNotIn("plot_outline", config)
                self.assertNotIn("plot_version", config)
                self.assertEqual(plot_payload["plot_outline"], "stored plot")
                self.assertEqual(plot_payload["plot_version"], "1")

    def test_save_plot_outline_updates_plot_store_and_legacy_shadow_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)), patch.object(
                plot_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
            ):
                manager = ContextManager(project_name="sample")
                manager.config_path.write_text(
                    json.dumps(
                        {
                            **context_module.DEFAULT_CONFIG,
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

                config = manager.get_config()
                story_bible = StoryBibleStore(project_name="sample").load()

                self.assertEqual(config["state"], "next confrontation is unavoidable")
                self.assertEqual(config["summary_of_previous"], "the hero escaped with the contract")
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
                manager.save_config(
                    {
                        **context_module.DEFAULT_CONFIG,
                        "worldview": "world data",
                        "tone_and_manner": "tone guide",
                        "continuity": "fixed rules",
                        "state": "current state",
                        "summary_of_previous": "previous summary",
                    }
                )
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
