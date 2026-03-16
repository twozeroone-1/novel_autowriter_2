import json
import tempfile
import unittest
from pathlib import Path

from core.context_story_bible_shadow import (
    DEFAULT_STORY_BIBLE_SHADOW,
    load_story_bible_shadow_payload,
    write_story_bible_shadow,
)


class TestContextStoryBibleShadow(unittest.TestCase):
    def test_load_story_bible_shadow_payload_normalizes_missing_and_non_string_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text('{"worldview": 123, "state": null}', encoding="utf-8")

            payload = load_story_bible_shadow_payload(config_path)

            self.assertEqual(payload["worldview"], "123")
            self.assertEqual(payload["tone_and_manner"], DEFAULT_STORY_BIBLE_SHADOW["tone_and_manner"])
            self.assertEqual(payload["continuity"], DEFAULT_STORY_BIBLE_SHADOW["continuity"])

    def test_write_story_bible_shadow_preserves_non_story_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps({"state": "kept", "summary_of_previous": "kept"}, ensure_ascii=False),
                encoding="utf-8",
            )

            write_story_bible_shadow(
                config_path,
                worldview="new world",
                tone_and_manner="new style",
                continuity="new rules",
            )

            payload = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "kept")
            self.assertEqual(payload["summary_of_previous"], "kept")
            self.assertEqual(payload["worldview"], "new world")
            self.assertEqual(payload["tone_and_manner"], "new style")
            self.assertEqual(payload["continuity"], "new rules")


if __name__ == "__main__":
    unittest.main()
