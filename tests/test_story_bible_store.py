import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.story_bible_store as story_bible_store_module
from core.story_bible_store import StoryBibleStore


class TestStoryBibleStore(unittest.TestCase):
    def test_load_story_bible_returns_default_sections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = StoryBibleStore(project_name="sample")

                story_bible = store.load()

                self.assertIn("worldview", story_bible)
                self.assertIn("style_guide", story_bible)
                self.assertIn("fixed_rules", story_bible)
                self.assertIn("author_intent", story_bible)
                self.assertEqual(story_bible["author_intent"], "")

    def test_save_story_bible_normalizes_missing_sections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = StoryBibleStore(project_name="sample")

                store.save(
                    {
                        "worldview": "closed world",
                        "style_guide": 12,
                    }
                )

                reloaded = store.load()

                self.assertEqual(reloaded["worldview"], "closed world")
                self.assertEqual(reloaded["style_guide"], "12")
                self.assertEqual(reloaded["fixed_rules"], story_bible_store_module.DEFAULT_STORY_BIBLE["fixed_rules"])
                self.assertEqual(reloaded["author_intent"], "")

    def test_export_prompt_sections_formats_story_bible_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(story_bible_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = StoryBibleStore(project_name="sample")
                store.save(
                    {
                        **story_bible_store_module.DEFAULT_STORY_BIBLE,
                        "worldview": "academy city",
                        "style_guide": "dry voice",
                        "fixed_rules": "no regression",
                    }
                )

                block = store.export_prompt_sections()

                self.assertIn("[STORY BIBLE]", block)
                self.assertIn("academy city", block)
                self.assertIn("[STYLE GUIDE]", block)
                self.assertIn("dry voice", block)
                self.assertIn("[FIXED RULES]", block)
                self.assertIn("no regression", block)


if __name__ == "__main__":
    unittest.main()
