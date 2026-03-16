import json
import tempfile
import unittest
from pathlib import Path

from core.context_state_shadow import load_state_shadow_snapshot, write_legacy_state_shadow
from core.context_state_store import DEFAULT_CONTEXT_STATE


class TestContextStateShadow(unittest.TestCase):
    def test_load_state_shadow_snapshot_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            snapshot = load_state_shadow_snapshot(config_path)

            self.assertEqual(snapshot, DEFAULT_CONTEXT_STATE)

    def test_write_legacy_state_shadow_updates_only_target_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps({"worldview": "kept"}, ensure_ascii=False), encoding="utf-8")

            write_legacy_state_shadow(config_path, state="new state", summary_of_previous=None)

            payload = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["worldview"], "kept")
            self.assertEqual(payload["state"], "new state")
            self.assertNotIn("summary_of_previous", payload)


if __name__ == "__main__":
    unittest.main()
