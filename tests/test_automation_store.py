import importlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestAutomationStore(unittest.TestCase):
    def test_load_automation_config_returns_defaults_when_missing(self):
        spec = importlib.util.find_spec("core.automation_store")
        self.assertIsNotNone(spec, "core.automation_store should exist")
        module = importlib.import_module("core.automation_store")
        store_cls = getattr(module, "AutomationStore", None)
        self.assertIsNotNone(store_cls, "AutomationStore should exist")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir):
                store = store_cls(project_name="sample")
                config = store.load_config()

        self.assertFalse(config["enabled"])
        self.assertEqual(config["schedule"]["type"], "daily")
        self.assertFalse(config["generation_options"]["include_plot"])
        self.assertEqual(config["generation_options"]["plot_strength"], "balanced")

    def test_load_automation_config_defaults_disable_legacy_context_updates(self):
        module = importlib.import_module("core.automation_store")
        store_cls = getattr(module, "AutomationStore", None)
        self.assertIsNotNone(store_cls, "AutomationStore should exist")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir):
                store = store_cls(project_name="sample")
                config = store.load_config()

        self.assertFalse(config["context_updates"]["state"])
        self.assertFalse(config["context_updates"]["summary"])

    def test_load_automation_config_merges_nested_generation_options_defaults(self):
        module = importlib.import_module("core.automation_store")
        store_cls = getattr(module, "AutomationStore", None)
        self.assertIsNotNone(store_cls, "AutomationStore should exist")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir):
                store = store_cls(project_name="sample")
                store.save_config(
                    {
                        "enabled": True,
                        "generation_options": {
                            "include_plot": True,
                        },
                    }
                )
                config = store.load_config()

        self.assertTrue(config["generation_options"]["include_plot"])
        self.assertEqual(config["generation_options"]["plot_strength"], "balanced")

    def test_save_and_load_queue_round_trips_jobs(self):
        module = importlib.import_module("core.automation_store")
        store_cls = getattr(module, "AutomationStore", None)
        self.assertIsNotNone(store_cls, "AutomationStore should exist")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir):
                store = store_cls(project_name="sample")
                self.assertTrue(hasattr(store, "save_queue"), "save_queue should exist")
                self.assertTrue(hasattr(store, "load_queue"), "load_queue should exist")

                jobs = [{"id": "job1", "title": "Episode 12", "status": "pending"}]
                store.save_queue(jobs)
                loaded = store.load_queue()

        self.assertEqual(loaded[0]["id"], "job1")

    def test_append_history_writes_jsonl(self):
        module = importlib.import_module("core.automation_store")
        store_cls = getattr(module, "AutomationStore", None)
        self.assertIsNotNone(store_cls, "AutomationStore should exist")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir):
                store = store_cls(project_name="sample")
                self.assertTrue(hasattr(store, "append_history"), "append_history should exist")
                self.assertTrue(hasattr(store, "load_recent_history"), "load_recent_history should exist")

                store.append_history({"job_id": "job1", "success": True})
                history = store.load_recent_history(limit=10)

        self.assertEqual(len(history), 1)


if __name__ == "__main__":
    unittest.main()
