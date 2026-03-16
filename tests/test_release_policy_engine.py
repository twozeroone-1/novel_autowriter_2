import unittest
from datetime import datetime, timezone

from core.release_policy_engine import evaluate_release_policy


class TestReleasePolicyEngine(unittest.TestCase):
    def test_evaluate_release_policy_skips_when_runtime_is_stopped(self):
        decision = evaluate_release_policy(
            policy={
                "global": {"burst_allowed": False, "stop_after_quality_incidents": 2},
                "platforms": {"munpia": {"enabled": True, "max_daily_releases": 1}},
            },
            runtime={"status": "stopped", "last_run_at": None, "last_error": "quality incidents"},
            history=[],
            now=datetime(2026, 3, 16, 21, 0, tzinfo=timezone.utc),
            force=False,
        )

        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "stopped")
        self.assertEqual(decision["next_runtime_status"], "stopped")

    def test_evaluate_release_policy_skips_when_runtime_is_paused(self):
        decision = evaluate_release_policy(
            policy={
                "global": {"burst_allowed": False},
                "platforms": {"munpia": {"enabled": True, "max_daily_releases": 1}},
            },
            runtime={"status": "paused", "last_run_at": None},
            history=[],
            now=datetime(2026, 3, 16, 21, 0, tzinfo=timezone.utc),
            force=False,
        )

        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "paused")
        self.assertEqual(decision["next_runtime_status"], "paused")

    def test_evaluate_release_policy_locks_burst_slot_until_first_same_day_success(self):
        decision = evaluate_release_policy(
            policy={
                "global": {"burst_allowed": True},
                "platforms": {"munpia": {"enabled": True, "max_daily_releases": 2}},
            },
            runtime={"status": "idle", "last_run_at": None},
            history=[],
            now=datetime(2026, 3, 16, 21, 0, tzinfo=timezone.utc),
            force=False,
        )

        self.assertEqual(decision["action"], "run_now")
        self.assertFalse(decision["burst_slot"])
        self.assertEqual(decision["allowed_platforms"], ["munpia"])

    def test_evaluate_release_policy_opens_second_slot_after_first_same_day_success(self):
        history = [
            {
                "timestamp": "2026-03-16T09:00:00+00:00",
                "success": True,
                "platform_results": {
                    "munpia": {"success": True, "status": "done"},
                },
            }
        ]

        decision = evaluate_release_policy(
            policy={
                "global": {"burst_allowed": True},
                "platforms": {"munpia": {"enabled": True, "max_daily_releases": 2}},
            },
            runtime={"status": "idle", "last_run_at": "2026-03-16T09:00:00+00:00"},
            history=history,
            now=datetime(2026, 3, 16, 21, 0, tzinfo=timezone.utc),
            force=False,
        )

        self.assertEqual(decision["action"], "run_now")
        self.assertTrue(decision["burst_slot"])
        self.assertEqual(decision["allowed_platforms"], ["munpia"])

    def test_evaluate_release_policy_blocks_after_quality_hard_fail(self):
        decision = evaluate_release_policy(
            policy={
                "global": {"burst_allowed": False},
                "platforms": {"munpia": {"enabled": True, "max_daily_releases": 1}},
            },
            runtime={"status": "blocked", "last_run_at": "2026-03-16T21:00:00+00:00", "last_error": "bad title"},
            history=[],
            now=datetime(2026, 3, 16, 21, 5, tzinfo=timezone.utc),
            force=False,
        )

        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "blocked")
        self.assertEqual(decision["next_runtime_status"], "blocked")

    def test_evaluate_release_policy_stops_after_repeated_quality_incidents(self):
        history = [
            {
                "timestamp": "2026-03-16T20:00:00+00:00",
                "incident_type": "quality_incident",
                "success": False,
                "platform_results": {},
            },
            {
                "timestamp": "2026-03-16T19:00:00+00:00",
                "incident_type": "quality_incident",
                "success": False,
                "platform_results": {},
            },
        ]

        decision = evaluate_release_policy(
            policy={
                "global": {"burst_allowed": False, "stop_after_quality_incidents": 2},
                "platforms": {"munpia": {"enabled": True, "max_daily_releases": 1}},
            },
            runtime={"status": "idle", "last_run_at": "2026-03-16T20:00:00+00:00"},
            history=history,
            now=datetime(2026, 3, 16, 21, 0, tzinfo=timezone.utc),
            force=False,
        )

        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "stopped")
        self.assertEqual(decision["next_runtime_status"], "stopped")

    def test_evaluate_release_policy_cools_down_until_next_schedule_window(self):
        decision = evaluate_release_policy(
            policy={
                "global": {"burst_allowed": False},
                "platforms": {"munpia": {"enabled": True, "max_daily_releases": 1}},
            },
            runtime={"status": "cooldown", "last_run_at": "2026-03-16T20:30:00+00:00"},
            history=[],
            now=datetime(2026, 3, 16, 20, 45, tzinfo=timezone.utc),
            force=False,
            schedule={"type": "daily", "time": "21:00"},
        )

        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "cooldown")
        self.assertEqual(decision["next_runtime_status"], "cooldown")

    def test_evaluate_release_policy_skips_when_platform_hit_daily_limit(self):
        history = [
            {
                "timestamp": "2026-03-16T09:00:00+00:00",
                "success": True,
                "platform_results": {
                    "munpia": {"success": True, "status": "done"},
                },
            }
        ]

        decision = evaluate_release_policy(
            policy={
                "global": {"burst_allowed": False},
                "platforms": {"munpia": {"enabled": True, "max_daily_releases": 2}},
            },
            runtime={"status": "idle", "last_run_at": "2026-03-16T09:00:00+00:00"},
            history=history,
            now=datetime(2026, 3, 16, 21, 0, tzinfo=timezone.utc),
            force=False,
        )

        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "no_allowed_platforms")
        self.assertEqual(decision["blocked_platforms"]["munpia"], "daily_limit_reached")

    def test_evaluate_release_policy_allows_only_platforms_matching_current_time_window(self):
        decision = evaluate_release_policy(
            policy={
                "global": {"burst_allowed": False},
                "platforms": {
                    "munpia": {
                        "enabled": True,
                        "max_daily_releases": 1,
                        "default_times": ["21:00"],
                    },
                    "novelpia": {
                        "enabled": True,
                        "max_daily_releases": 1,
                        "default_times": ["20:00"],
                    },
                },
            },
            runtime={"status": "idle", "last_run_at": None},
            history=[],
            now=datetime(2026, 3, 16, 21, 0, tzinfo=timezone.utc),
            force=False,
        )

        self.assertEqual(decision["action"], "run_now")
        self.assertEqual(decision["allowed_platforms"], ["munpia"])
        self.assertEqual(decision["blocked_platforms"]["novelpia"], "outside_release_window")

    def test_evaluate_release_policy_skips_when_no_platform_matches_time_window(self):
        decision = evaluate_release_policy(
            policy={
                "global": {"burst_allowed": False},
                "platforms": {
                    "munpia": {
                        "enabled": True,
                        "max_daily_releases": 1,
                        "default_times": ["07:00"],
                    },
                    "novelpia": {
                        "enabled": True,
                        "max_daily_releases": 1,
                        "default_times": ["20:00"],
                    },
                },
            },
            runtime={"status": "idle", "last_run_at": None},
            history=[],
            now=datetime(2026, 3, 16, 21, 0, tzinfo=timezone.utc),
            force=False,
        )

        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "no_allowed_platforms")
        self.assertEqual(decision["blocked_platforms"]["munpia"], "outside_release_window")
        self.assertEqual(decision["blocked_platforms"]["novelpia"], "outside_release_window")

    def test_evaluate_release_policy_blocks_only_platform_with_repeated_platform_incidents(self):
        history = [
            {
                "timestamp": "2026-03-16T20:00:00+00:00",
                "incident_type": "platform_incident",
                "success": False,
                "platform_results": {
                    "munpia": {"success": False, "status": "failed"},
                },
            },
            {
                "timestamp": "2026-03-16T19:00:00+00:00",
                "incident_type": "platform_incident",
                "success": False,
                "platform_results": {
                    "munpia": {"success": False, "status": "failed"},
                },
            },
        ]

        decision = evaluate_release_policy(
            policy={
                "global": {
                    "burst_allowed": False,
                    "block_platform_after_platform_incidents": 2,
                },
                "platforms": {
                    "munpia": {"enabled": True, "max_daily_releases": 1},
                    "novelpia": {"enabled": True, "max_daily_releases": 1},
                },
            },
            runtime={"status": "idle", "last_run_at": "2026-03-16T20:00:00+00:00"},
            history=history,
            now=datetime(2026, 3, 16, 21, 0, tzinfo=timezone.utc),
            force=False,
        )

        self.assertEqual(decision["action"], "run_now")
        self.assertEqual(decision["allowed_platforms"], ["novelpia"])
        self.assertEqual(decision["blocked_platforms"]["munpia"], "incident_threshold_reached")


if __name__ == "__main__":
    unittest.main()
