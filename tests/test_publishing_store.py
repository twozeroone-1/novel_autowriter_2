import importlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestPublishingStore(unittest.TestCase):
    def test_load_publishing_config_returns_defaults_when_missing(self):
        spec = importlib.util.find_spec("core.publishing_store")
        self.assertIsNotNone(spec, "core.publishing_store should exist")
        module = importlib.import_module("core.publishing_store")
        store_cls = getattr(module, "PublishingStore", None)
        self.assertIsNotNone(store_cls, "PublishingStore should exist")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir):
                store = store_cls(project_name="sample")
                config = store.load_config()

        self.assertFalse(config["enabled"])
        self.assertEqual(config["schedule"]["type"], "daily")
        self.assertFalse(config["platforms"]["munpia"]["enabled"])
        self.assertFalse(config["platforms"]["novelpia"]["enabled"])

    def test_load_config_bootstraps_config_file_when_missing(self):
        module = importlib.import_module("core.publishing_store")
        store_cls = getattr(module, "PublishingStore", None)
        self.assertIsNotNone(store_cls, "PublishingStore should exist")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir):
                store = store_cls(project_name="sample")
                self.assertFalse(store.config_path.exists())

                _ = store.load_config()

                self.assertTrue(store.config_path.exists())

    def test_bootstrapped_config_file_contains_default_structure(self):
        module = importlib.import_module("core.publishing_store")
        store_cls = getattr(module, "PublishingStore", None)
        self.assertIsNotNone(store_cls, "PublishingStore should exist")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir):
                store = store_cls(project_name="sample")
                config = store.load_config()
                saved = module.json.loads(store.config_path.read_text(encoding="utf-8"))

        self.assertEqual(saved["enabled"], config["enabled"])
        self.assertIn("platforms", saved)
        self.assertIn("munpia", saved["platforms"])
        self.assertIn("novelpia", saved["platforms"])
        self.assertIn("upload_url_template", saved["platforms"]["munpia"])

    def test_save_and_load_queue_round_trip(self):
        module = importlib.import_module("core.publishing_store")
        store_cls = getattr(module, "PublishingStore", None)
        self.assertIsNotNone(store_cls, "PublishingStore should exist")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir):
                store = store_cls(project_name="sample")
                self.assertTrue(hasattr(store, "save_queue"), "save_queue should exist")
                self.assertTrue(hasattr(store, "load_queue"), "load_queue should exist")

                jobs = [
                    {
                        "id": "pub_1",
                        "chapter_title": "Episode 12",
                        "status": "pending",
                    }
                ]
                store.save_queue(jobs)
                loaded = store.load_queue()

        self.assertEqual(loaded[0]["id"], "pub_1")

    def test_save_and_load_runtime_round_trip(self):
        module = importlib.import_module("core.publishing_store")
        store_cls = getattr(module, "PublishingStore", None)
        self.assertIsNotNone(store_cls, "PublishingStore should exist")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir):
                store = store_cls(project_name="sample")
                runtime = {
                    "status": "paused",
                    "current_job_id": "pub_1",
                    "last_error": "login failed",
                }
                store.save_runtime(runtime)
                loaded = store.load_runtime()

        self.assertEqual(loaded["status"], "paused")
        self.assertEqual(loaded["current_job_id"], "pub_1")

    def test_append_history_writes_jsonl(self):
        module = importlib.import_module("core.publishing_store")
        store_cls = getattr(module, "PublishingStore", None)
        self.assertIsNotNone(store_cls, "PublishingStore should exist")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir):
                store = store_cls(project_name="sample")
                self.assertTrue(hasattr(store, "append_history"), "append_history should exist")
                self.assertTrue(hasattr(store, "load_recent_history"), "load_recent_history should exist")

                store.append_history({"job_id": "pub_1", "success": True})
                history = store.load_recent_history(limit=10)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["job_id"], "pub_1")

    def test_load_config_keeps_nested_platform_defaults(self):
        module = importlib.import_module("core.publishing_store")
        store_cls = getattr(module, "PublishingStore", None)
        self.assertIsNotNone(store_cls, "PublishingStore should exist")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir):
                store = store_cls(project_name="sample")
                store.save_config(
                    {
                        "enabled": True,
                        "platforms": {
                            "munpia": {
                                "enabled": True,
                            }
                        },
                    }
                )
                config = store.load_config()

        self.assertTrue(config["platforms"]["munpia"]["enabled"])
        self.assertIn("default_publish_visibility", config["platforms"]["munpia"])
        self.assertIn("novelpia", config["platforms"])


if __name__ == "__main__":
    unittest.main()
