import importlib
import importlib.util
import sys
import types
import unittest
from unittest.mock import patch


def _install_fake_streamlit():
    fake_streamlit = types.SimpleNamespace(
        text_area=lambda *args, **kwargs: None,
        checkbox=lambda *args, **kwargs: False,
        selectbox=lambda *args, **kwargs: None,
        number_input=lambda *args, **kwargs: 0,
        time_input=lambda *args, **kwargs: None,
        multiselect=lambda *args, **kwargs: [],
        button=lambda *args, **kwargs: False,
        form=lambda *args, **kwargs: None,
        form_submit_button=lambda *args, **kwargs: False,
        columns=lambda *args, **kwargs: [],
        metric=lambda *args, **kwargs: None,
        divider=lambda *args, **kwargs: None,
        subheader=lambda *args, **kwargs: None,
        header=lambda *args, **kwargs: None,
        caption=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        success=lambda *args, **kwargs: None,
        dataframe=lambda *args, **kwargs: None,
        write=lambda *args, **kwargs: None,
        rerun=lambda *args, **kwargs: None,
        expander=lambda *args, **kwargs: None,
        session_state={},
    )
    sys.modules["streamlit"] = fake_streamlit


class TestPublishingUi(unittest.TestCase):
    def _load_module(self):
        spec = importlib.util.find_spec("ui.publishing")
        self.assertIsNotNone(spec, "ui.publishing should exist")
        _install_fake_streamlit()
        sys.modules.pop("ui.publishing", None)
        return importlib.import_module("ui.publishing")

    def test_format_publishing_schedule_summary_for_daily_rule(self):
        module = self._load_module()
        config = {
            "enabled": True,
            "schedule": {
                "type": "daily",
                "time": "21:30",
            },
        }

        summary = module.format_publishing_schedule_summary(config)

        self.assertEqual(summary, "매일 21:30")

    def test_build_publishing_queue_rows_handles_partial_platform_selection(self):
        module = self._load_module()
        rows = module.build_publishing_queue_rows(
            [
                {
                    "chapter_title": "Episode 12",
                    "status": "partial_failed",
                    "attempt_count": 1,
                    "targets": {
                        "munpia": {"selected": True},
                        "novelpia": {"selected": False},
                    },
                }
            ]
        )

        self.assertEqual(rows[0]["순서"], 1)
        self.assertEqual(rows[0]["회차"], "Episode 12")
        self.assertEqual(rows[0]["상태"], "partial_failed")
        self.assertEqual(rows[0]["대상"], "문피아")
        self.assertEqual(rows[0]["시도"], 1)

    def test_format_publishing_runtime_status_reports_paused_error(self):
        module = self._load_module()
        runtime = {
            "status": "paused",
            "last_error": "login failed",
        }

        status = module.format_publishing_runtime_status(runtime)

        self.assertEqual(status, "일시중지: login failed")

    def test_format_publishing_runtime_status_reports_cooldown_error(self):
        module = self._load_module()
        runtime = {
            "status": "cooldown",
            "last_error": "timeout",
        }

        status = module.format_publishing_runtime_status(runtime)

        self.assertEqual(status, "쿨다운: timeout")

    def test_format_publishing_runtime_status_reports_blocked_error(self):
        module = self._load_module()
        runtime = {
            "status": "blocked",
            "last_error": "no selected targets",
        }

        status = module.format_publishing_runtime_status(runtime)

        self.assertEqual(status, "차단됨: no selected targets")

    def test_format_publishing_runtime_status_reports_stopped_error(self):
        module = self._load_module()
        runtime = {
            "status": "stopped",
            "last_error": "quality incidents reached threshold",
        }

        status = module.format_publishing_runtime_status(runtime)

        self.assertEqual(status, "중단됨: quality incidents reached threshold")

    def test_format_publishing_runtime_status_reports_scheduled_waiting(self):
        module = self._load_module()
        runtime = {
            "status": "scheduled",
            "last_error": "",
        }

        status = module.format_publishing_runtime_status(runtime)

        self.assertEqual(status, "예약 대기")

    def test_build_publishing_history_summary_counts_total_success_and_failure(self):
        module = self._load_module()

        summary = module.build_publishing_history_summary(
            [
                {"success": True},
                {"success": False},
                {"success": True},
            ]
        )

        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["success"], 2)
        self.assertEqual(summary["failure"], 1)

    def test_summarize_selected_platforms_returns_both_labels(self):
        module = self._load_module()

        summary = module.summarize_selected_platforms(
            {
                "munpia": {"selected": True},
                "novelpia": {"selected": True},
            }
        )

        self.assertEqual(summary, "문피아, 노벨피아")

    def test_count_pending_publishing_jobs_counts_pending_and_partial_failed(self):
        module = self._load_module()

        count = module.count_pending_publishing_jobs(
            [
                {"status": "pending"},
                {"status": "partial_failed"},
                {"status": "scheduled"},
                {"status": "done"},
            ]
        )

        self.assertEqual(count, 3)

    def test_build_publishing_queue_rows_preserves_scheduled_status(self):
        module = self._load_module()

        rows = module.build_publishing_queue_rows(
            [
                {
                    "chapter_title": "Episode 21",
                    "status": "scheduled",
                    "attempt_count": 1,
                    "targets": {
                        "novelpia": {"selected": True},
                    },
                }
            ]
        )

        self.assertEqual(rows[0]["상태"], "scheduled")
        self.assertEqual(rows[0]["대상"], "노벨피아")

    def test_build_publishing_history_rows_formats_platform_summary(self):
        module = self._load_module()

        rows = module.build_publishing_history_rows(
            [
                {
                    "timestamp": "2026-03-12T21:00:00+09:00",
                    "chapter_title": "Episode 12",
                    "success": False,
                    "platform_results": {
                        "munpia": {"success": True},
                        "novelpia": {"success": False},
                    },
                }
            ]
        )

        self.assertEqual(rows[0]["결과"], "실패")
        self.assertEqual(rows[0]["플랫폼"], "문피아, 노벨피아")

    def test_build_publishing_history_rows_labels_scheduled_results(self):
        module = self._load_module()

        rows = module.build_publishing_history_rows(
            [
                {
                    "timestamp": "2026-03-16T22:00:00+09:00",
                    "chapter_title": "Episode 20",
                    "success": False,
                    "platform_results": {
                        "novelpia": {"status": "scheduled", "success": True},
                    },
                }
            ]
        )

        self.assertEqual(rows[0]["결과"], "예약")

    def test_get_unsupported_publish_mode_platforms_flags_munpia_for_reserved(self):
        module = self._load_module()

        unsupported = module.get_unsupported_publish_mode_platforms(
            selected_platforms=["munpia", "novelpia"],
            publish_mode="reserved",
        )

        self.assertEqual(unsupported, ["munpia"])

    def test_get_unsupported_publish_mode_platforms_allows_mixed_immediate_mode(self):
        module = self._load_module()

        unsupported = module.get_unsupported_publish_mode_platforms(
            selected_platforms=["munpia", "novelpia"],
            publish_mode="immediate",
        )

        self.assertEqual(unsupported, [])

    def test_build_platform_readiness_rows_marks_missing_credentials_and_mapping(self):
        module = self._load_module()

        rows = module.build_platform_readiness_rows(
            project_name="sample",
            config={
                "platforms": {
                    "munpia": {
                        "enabled": True,
                        "work_id": "",
                        "upload_url_template": "",
                    }
                }
            },
            credential_loader=lambda _project, _platform: {"username": "", "password": ""},
        )

        self.assertEqual(rows[0]["platform_name"], "munpia")
        self.assertFalse(rows[0]["ready"])
        self.assertFalse(rows[0]["has_credentials"])
        self.assertFalse(rows[0]["has_work_id"])
        self.assertFalse(rows[0]["has_upload_url_template"])

    def test_build_platform_readiness_rows_marks_ready_platform(self):
        module = self._load_module()

        rows = module.build_platform_readiness_rows(
            project_name="sample",
            config={
                "platforms": {
                    "novelpia": {
                        "enabled": True,
                        "work_id": "416704",
                        "upload_url_template": "https://example.test/upload/{work_id}",
                    }
                }
            },
            credential_loader=lambda _project, _platform: {"username": "writer", "password": "secret"},
        )

        self.assertEqual(rows[1]["platform_name"], "novelpia")
        self.assertTrue(rows[1]["ready"])
        self.assertTrue(rows[1]["has_credentials"])
        self.assertTrue(rows[1]["has_work_id"])
        self.assertTrue(rows[1]["has_upload_url_template"])

    def test_build_publishing_operations_snapshot_prioritizes_configuration_action_when_platform_not_ready(self):
        module = self._load_module()

        snapshot = module.build_publishing_operations_snapshot(
            project_name="sample",
            config={
                "enabled": True,
                "schedule": {"type": "daily", "time": "21:00"},
                "platforms": {
                    "munpia": {
                        "enabled": True,
                        "work_id": "",
                        "upload_url_template": "",
                    }
                },
            },
            runtime={"status": "idle", "last_error": ""},
            queue=[{"status": "pending"}],
            history=[],
            credential_loader=lambda _project, _platform: {"username": "", "password": ""},
        )

        self.assertFalse(snapshot["publishing_ready"])
        self.assertEqual(snapshot["next_actions"][0], "플랫폼 계정과 작품 매핑을 먼저 완료하세요.")

    def test_build_publishing_operations_snapshot_uses_shared_readiness_snapshot(self):
        module = self._load_module()

        shared_snapshot = {
            "platform_rows": (
                {
                    "platform_name": "munpia",
                    "platform_label": "문피아",
                    "enabled": True,
                    "has_credentials": False,
                    "has_work_id": False,
                    "has_upload_url_template": False,
                    "ready": False,
                },
            ),
            "enabled_platform_count": 1,
            "ready_platform_count": 0,
            "publishing_ready": False,
            "blockers": ("shared blocker",),
            "recommended_actions": ("shared action",),
        }

        with patch.object(module, "build_publishing_readiness_snapshot", return_value=shared_snapshot) as mocked_build:
            snapshot = module.build_publishing_operations_snapshot(
                project_name="sample",
                config={"enabled": True, "schedule": {"type": "daily", "time": "21:00"}, "platforms": {}},
                runtime={"status": "idle", "last_error": ""},
                queue=[],
                history=[],
                credential_loader=lambda _project, _platform: {"username": "", "password": ""},
            )

        mocked_build.assert_called_once()
        self.assertEqual(snapshot["platform_rows"], shared_snapshot["platform_rows"])
        self.assertIn("shared blocker", snapshot["blockers"])
        self.assertIn("shared action", snapshot["next_actions"])

    def test_build_munpia_session_snapshot_reports_missing_session_and_command(self):
        module = self._load_module()

        with patch.object(module, "build_bootstrap_command", return_value="python3 scripts/bootstrap_munpia_session.py 2"), patch.object(
            module, "PlatformSessionStore"
        ) as store_cls:
            store_cls.return_value.session_state_path.return_value.exists.return_value = False
            store_cls.return_value.session_state_path.return_value = store_cls.return_value.session_state_path.return_value

            snapshot = module.build_munpia_session_snapshot(project_name="2")

        self.assertFalse(snapshot["has_saved_session"])
        self.assertIn("bootstrap_munpia_session.py 2", snapshot["command"])

    def test_build_publishing_operations_snapshot_adds_munpia_session_action_when_missing(self):
        module = self._load_module()

        with patch.object(module, "build_munpia_session_snapshot", return_value={"has_saved_session": False}):
            snapshot = module.build_publishing_operations_snapshot(
                project_name="sample",
                config={
                    "enabled": True,
                    "schedule": {"type": "daily", "time": "21:00"},
                    "platforms": {
                        "munpia": {
                            "enabled": True,
                            "work_id": "549287",
                            "upload_url_template": "https://example.test/{work_id}",
                        }
                    },
                },
                runtime={"status": "idle", "last_error": ""},
                queue=[],
                history=[],
                credential_loader=lambda _project, _platform: {"username": "writer", "password": "secret"},
            )

        self.assertIn("문피아 수동 로그인 세션을 먼저 저장하세요.", snapshot["next_actions"])


if __name__ == "__main__":
    unittest.main()
