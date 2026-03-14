import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.run_snapshot_store as run_snapshot_store_module
from core.run_snapshot_store import RunSnapshotStore


class TestRunSnapshotStore(unittest.TestCase):
    def test_create_run_directory_and_write_named_snapshots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(run_snapshot_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = RunSnapshotStore(project_name="sample")

                run_id = store.create_run_id(prefix="origin")
                json_path = store.write_json_snapshot(run_id, "input_snapshot.json", {"episode_id": "ep_001"})
                text_path = store.write_text_snapshot(run_id, "prompt.txt", "hello")

                self.assertTrue(json_path.exists())
                self.assertTrue(text_path.exists())
                self.assertIn("origin_", run_id)

    def test_snapshot_store_preserves_serializable_payloads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(run_snapshot_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = RunSnapshotStore(project_name="sample")

                run_id = store.create_run_id()
                json_path = store.write_json_snapshot(
                    run_id,
                    "quality_report.json",
                    {"status": "passed", "errors": []},
                )

                payload = json.loads(json_path.read_text(encoding="utf-8"))
                self.assertEqual(payload["status"], "passed")
                self.assertEqual(payload["errors"], [])


if __name__ == "__main__":
    unittest.main()
