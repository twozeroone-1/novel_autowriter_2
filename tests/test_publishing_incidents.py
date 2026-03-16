import importlib
import importlib.util
import unittest


class TestPublishingIncidents(unittest.TestCase):
    def _load_summarizer(self):
        spec = importlib.util.find_spec("core.publishing_incidents")
        self.assertIsNotNone(spec, "core.publishing_incidents should exist")
        module = importlib.import_module("core.publishing_incidents")
        summarizer = getattr(module, "summarize_publish_attempt", None)
        self.assertIsNotNone(summarizer, "summarize_publish_attempt should exist")
        return summarizer

    def test_summarize_publish_attempt_marks_done_and_idle_when_all_selected_targets_succeed(self):
        summarize_publish_attempt = self._load_summarizer()

        summary = summarize_publish_attempt(
            job={"targets": {"munpia": {"selected": True, "status": "done"}}},
            platform_results={"munpia": {"status": "done", "success": True}},
        )

        self.assertEqual(summary["job_status"], "done")
        self.assertEqual(summary["runtime_status"], "idle")
        self.assertEqual(summary["incident_type"], "")

    def test_summarize_publish_attempt_treats_scheduled_as_success(self):
        summarize_publish_attempt = self._load_summarizer()

        summary = summarize_publish_attempt(
            job={"targets": {"novelpia": {"selected": True, "status": "scheduled"}}},
            platform_results={"novelpia": {"status": "scheduled", "success": True}},
        )

        self.assertEqual(summary["job_status"], "done")
        self.assertEqual(summary["runtime_status"], "idle")
        self.assertEqual(summary["incident_type"], "")

    def test_summarize_publish_attempt_marks_paused_for_requires_user_action(self):
        summarize_publish_attempt = self._load_summarizer()

        summary = summarize_publish_attempt(
            job={"targets": {"munpia": {"selected": True, "status": "failed"}}},
            platform_results={
                "munpia": {
                    "status": "failed",
                    "success": False,
                    "error_type": "requires_user_action",
                    "error_text": "captcha required",
                }
            },
        )

        self.assertEqual(summary["runtime_status"], "paused")
        self.assertEqual(summary["incident_type"], "credential_incident")

    def test_summarize_publish_attempt_marks_partial_failed_when_results_are_mixed(self):
        summarize_publish_attempt = self._load_summarizer()

        summary = summarize_publish_attempt(
            job={
                "targets": {
                    "munpia": {"selected": True, "status": "done"},
                    "novelpia": {"selected": True, "status": "failed"},
                }
            },
            platform_results={
                "munpia": {"status": "done", "success": True},
                "novelpia": {"status": "failed", "success": False, "error_type": "retryable", "error_text": "timeout"},
            },
        )

        self.assertEqual(summary["job_status"], "partial_failed")
        self.assertEqual(summary["runtime_status"], "cooldown")
        self.assertEqual(summary["incident_type"], "platform_incident")


if __name__ == "__main__":
    unittest.main()
