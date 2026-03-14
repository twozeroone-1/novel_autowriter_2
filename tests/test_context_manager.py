import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.canon_store as canon_store_module
import core.context as context_module
import core.release_policy_store as release_policy_store_module
import core.story_bible_store as story_bible_store_module
from core.canon_store import CanonStore
from core.context import ContextManager
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
                        "plot_outline": "plot outline text",
                    }
                )
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
                manager.save_config(
                    {
                        **context_module.DEFAULT_CONFIG,
                        "plot_outline": "plot outline text",
                    }
                )

                prompt = manager.build_generation_prompt(
                    "write next chapter",
                    include_plot=False,
                    plot_strength="strict",
                )

                self.assertNotIn("plot outline text", prompt)
                self.assertNotIn("[PLOT OUTLINE]", prompt)


if __name__ == "__main__":
    unittest.main()
