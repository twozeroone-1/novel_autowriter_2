import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.canon_store as canon_store_module
from core.canon_store import CanonStore


class TestCanonStore(unittest.TestCase):
    def test_load_current_state_returns_default_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(canon_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = CanonStore(project_name="sample")

                state = store.load_current_state()

                self.assertEqual(state["people"], {})
                self.assertEqual(state["resources"], {})
                self.assertEqual(state["hooks"], [])
                self.assertEqual(state["timeline"], [])

    def test_append_event_persists_jsonl_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(canon_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = CanonStore(project_name="sample")

                store.append_event({"episode_id": "ep_001", "kind": "publish_success"})

                lines = store.events_path.read_text(encoding="utf-8").splitlines()
                self.assertEqual(len(lines), 1)
                self.assertEqual(json.loads(lines[0])["episode_id"], "ep_001")

    def test_apply_state_update_merges_people_resources_and_hooks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(canon_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = CanonStore(project_name="sample")
                store.save_current_state(
                    {
                        "people": {"lead": {"mood": "calm"}},
                        "resources": {"cash": 10},
                        "hooks": ["old hook"],
                        "timeline": ["ep_000"],
                    }
                )

                updated = store.apply_state_update(
                    {
                        "people": {"lead": {"mood": "angry"}, "support": {"status": "active"}},
                        "resources": {"cash": 20, "fame": 3},
                        "hooks": ["new hook"],
                        "timeline": ["ep_001"],
                    }
                )

                self.assertEqual(updated["people"]["lead"]["mood"], "angry")
                self.assertEqual(updated["people"]["support"]["status"], "active")
                self.assertEqual(updated["resources"]["cash"], 20)
                self.assertEqual(updated["resources"]["fame"], 3)
                self.assertEqual(updated["hooks"], ["old hook", "new hook"])
                self.assertEqual(updated["timeline"], ["ep_000", "ep_001"])

    def test_write_snapshot_creates_episode_snapshot_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(canon_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = CanonStore(project_name="sample")

                snapshot_path = store.write_snapshot("ep_001", {"people": {}, "resources": {}, "hooks": [], "timeline": []})

                self.assertTrue(snapshot_path.exists())
                payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
                self.assertEqual(payload["people"], {})


if __name__ == "__main__":
    unittest.main()
