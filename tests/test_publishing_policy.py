import importlib
import importlib.util
import unittest
from datetime import datetime


class TestPublishingPolicy(unittest.TestCase):
    def _load_selector(self):
        spec = importlib.util.find_spec("core.publishing_policy")
        self.assertIsNotNone(spec, "core.publishing_policy should exist")
        module = importlib.import_module("core.publishing_policy")
        selector = getattr(module, "select_runnable_job", None)
        self.assertIsNotNone(selector, "select_runnable_job should exist")
        return selector

    def test_select_runnable_job_skips_when_disabled(self):
        select_runnable_job = self._load_selector()

        decision = select_runnable_job(
            config={"enabled": False, "schedule": {"type": "daily", "time": "21:00", "days": [], "hours": 24}},
            runtime={"status": "idle", "last_run_at": None},
            queue=[{"id": "job-1", "status": "pending"}],
            now=datetime(2026, 3, 16, 21, 0),
        )

        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "disabled")

    def test_select_runnable_job_skips_when_runtime_is_paused(self):
        select_runnable_job = self._load_selector()

        decision = select_runnable_job(
            config={"enabled": True, "schedule": {"type": "daily", "time": "21:00", "days": [], "hours": 24}},
            runtime={"status": "paused", "last_run_at": None},
            queue=[{"id": "job-1", "status": "pending"}],
            now=datetime(2026, 3, 16, 21, 0),
        )

        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "paused")

    def test_select_runnable_job_returns_first_pending_or_partial_failed_job_when_due(self):
        select_runnable_job = self._load_selector()

        decision = select_runnable_job(
            config={"enabled": True, "schedule": {"type": "daily", "time": "21:00", "days": [], "hours": 24}},
            runtime={"status": "idle", "last_run_at": None},
            queue=[
                {"id": "job-1", "status": "done"},
                {"id": "job-2", "status": "partial_failed"},
                {"id": "job-3", "status": "pending"},
            ],
            now=datetime(2026, 3, 16, 21, 0),
        )

        self.assertEqual(decision["action"], "run_now")
        self.assertEqual(decision["reason"], "")
        self.assertEqual(decision["job"]["id"], "job-2")


if __name__ == "__main__":
    unittest.main()
