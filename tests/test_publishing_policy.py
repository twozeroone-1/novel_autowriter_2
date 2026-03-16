import importlib
import importlib.util
import unittest
from datetime import datetime, timezone


class TestPublishingPolicy(unittest.TestCase):
    def _load_selector(self):
        spec = importlib.util.find_spec("core.publishing_policy")
        self.assertIsNotNone(spec, "core.publishing_policy should exist")
        module = importlib.import_module("core.publishing_policy")
        selector = getattr(module, "select_runnable_job", None)
        self.assertIsNotNone(selector, "select_runnable_job should exist")
        return selector

    def test_select_runnable_job_returns_first_job_with_allowed_selected_target(self):
        select_runnable_job = self._load_selector()

        decision = select_runnable_job(
            queue=[
                {"id": "job-1", "status": "pending", "targets": {"munpia": {"selected": True}}},
                {"id": "job-2", "status": "pending", "targets": {"novelpia": {"selected": True}}},
            ],
            allowed_platforms={"novelpia"},
        )

        self.assertEqual(decision["action"], "run_now")
        self.assertEqual(decision["job"]["id"], "job-2")

    def test_select_runnable_job_skips_when_no_job_matches_allowed_platforms(self):
        select_runnable_job = self._load_selector()

        decision = select_runnable_job(
            queue=[
                {"id": "job-1", "status": "pending", "targets": {"munpia": {"selected": True}}},
            ],
            allowed_platforms={"novelpia"},
        )

        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "no_job")

    def test_select_runnable_job_ignores_jobs_without_selected_allowed_targets(self):
        select_runnable_job = self._load_selector()

        decision = select_runnable_job(
            queue=[
                {"id": "job-1", "status": "partial_failed", "targets": {"munpia": {"selected": False}}},
                {"id": "job-2", "status": "done", "targets": {"novelpia": {"selected": True}}},
                {
                    "id": "job-3",
                    "status": "partial_failed",
                    "targets": {
                        "munpia": {"selected": True},
                        "novelpia": {"selected": False},
                    },
                },
            ],
            allowed_platforms={"munpia"},
        )

        self.assertEqual(decision["action"], "run_now")
        self.assertEqual(decision["job"]["id"], "job-3")

    def test_select_runnable_job_prioritizes_due_scheduled_job_before_pending(self):
        select_runnable_job = self._load_selector()

        decision = select_runnable_job(
            queue=[
                {
                    "id": "job-scheduled",
                    "status": "scheduled",
                    "targets": {
                        "novelpia": {
                            "selected": True,
                            "status": "scheduled",
                            "reserved_at": "2026-03-16T21:00:00+09:00",
                        }
                    },
                },
                {"id": "job-pending", "status": "pending", "targets": {"munpia": {"selected": True}}},
            ],
            allowed_platforms={"munpia"},
            now=datetime(2026, 3, 16, 12, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(decision["action"], "run_now")
        self.assertEqual(decision["job"]["id"], "job-scheduled")
        self.assertEqual(decision["mode"], "reconcile_scheduled")


if __name__ == "__main__":
    unittest.main()
