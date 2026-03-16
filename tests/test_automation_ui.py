import importlib
import importlib.util
import sys
import types
import unittest


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
        session_state={},
    )
    sys.modules["streamlit"] = fake_streamlit


class TestAutomationUi(unittest.TestCase):
    def _load_module(self):
        spec = importlib.util.find_spec("ui.automation")
        self.assertIsNotNone(spec, "ui.automation should exist")
        _install_fake_streamlit()
        sys.modules.pop("ui.automation", None)
        return importlib.import_module("ui.automation")

    def test_get_context_update_defaults_disable_legacy_auto_updates_when_missing(self):
        module = self._load_module()

        defaults = module.get_context_update_defaults({})

        self.assertFalse(defaults["state"])
        self.assertFalse(defaults["summary"])

    def test_format_context_update_policy_mentions_canon_recording_when_legacy_is_disabled(self):
        module = self._load_module()

        text = module.format_context_update_policy({"state": False, "summary": False})

        self.assertIn("레거시", text)
        self.assertIn("Canon", text)
        self.assertIn("자동 반영", text)

    def test_format_schedule_summary_for_weekly_rule(self):
        module = self._load_module()
        config = {
            "enabled": True,
            "schedule": {
                "type": "weekly",
                "time": "07:30",
                "days": ["mon", "wed", "fri"],
            },
        }

        summary = module.format_schedule_summary(config)

        self.assertEqual(summary, "매주 월, 수, 금 07:30")

    def test_format_schedule_summary_for_interval_rule(self):
        module = self._load_module()
        config = {
            "enabled": True,
            "schedule": {
                "type": "interval",
                "hours": 6,
            },
        }

        summary = module.format_schedule_summary(config)

        self.assertEqual(summary, "6시간마다 반복")

    def test_format_runtime_status_reports_paused_error(self):
        module = self._load_module()
        runtime = {
            "status": "paused",
            "last_error": "boom",
        }

        status = module.format_runtime_status(runtime)

        self.assertEqual(status, "일시중지: boom")

    def test_format_runtime_detail_value_uses_dash_for_empty_or_none(self):
        module = self._load_module()

        self.assertEqual(module.format_runtime_detail_value(None), "-")
        self.assertEqual(module.format_runtime_detail_value(""), "-")
        self.assertEqual(module.format_runtime_detail_value("job_1"), "job_1")

    def test_build_queue_rows_adds_order_and_defaults(self):
        module = self._load_module()
        rows = module.build_queue_rows(
            [
                {"title": "Episode 12", "status": "pending", "attempt_count": 0},
                {"title": "Episode 13", "status": "failed", "attempt_count": 2},
            ]
        )

        self.assertEqual(rows[0]["순서"], 1)
        self.assertEqual(rows[0]["제목"], "Episode 12")
        self.assertEqual(rows[1]["상태"], "failed")
        self.assertEqual(rows[1]["시도"], 2)

    def test_build_history_rows_formats_backend_and_result(self):
        module = self._load_module()
        rows = module.build_history_rows(
            [
                {
                    "timestamp": "2026-03-12T21:00:00+09:00",
                    "title": "Episode 12",
                    "success": True,
                    "backend": "cli",
                }
            ]
        )

        self.assertEqual(rows[0]["결과"], "성공")
        self.assertEqual(rows[0]["백엔드"], "cli")
        self.assertEqual(rows[0]["제목"], "Episode 12")

    def test_build_schedule_editor_state_for_interval(self):
        module = self._load_module()

        editor_state = module.build_schedule_editor_state("interval")

        self.assertFalse(editor_state["show_time"])
        self.assertFalse(editor_state["show_days"])
        self.assertTrue(editor_state["show_hours"])

    def test_build_history_summary_counts_total_success_and_failure(self):
        module = self._load_module()

        summary = module.build_history_summary(
            [
                {"success": True},
                {"success": False},
                {"success": True},
            ]
        )

        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["success"], 2)
        self.assertEqual(summary["failure"], 1)

    def test_build_automation_operations_snapshot_marks_warning_when_runtime_is_paused(self):
        module = self._load_module()

        snapshot = module.build_automation_operations_snapshot(
            config={
                "enabled": True,
                "schedule": {"type": "daily", "time": "21:00"},
            },
            queue=[],
            runtime={"status": "paused", "last_error": "captcha"},
            history=[],
            diagnostics_snapshot={
                "summary_text": "24시간 4건 / 실패 1건 / 최근 api",
                "status": "warning",
                "warning_text": "최근 진단 실패 1건",
            },
        )

        self.assertEqual(snapshot["runtime_status"], "일시중지: captcha")
        self.assertEqual(snapshot["pending_job_count"], 0)
        self.assertIn("일시중지", snapshot["blockers"][0])
        self.assertIn("paused", snapshot["next_actions"][0])

    def test_build_automation_operations_snapshot_prefers_queue_action_when_idle(self):
        module = self._load_module()

        snapshot = module.build_automation_operations_snapshot(
            config={
                "enabled": True,
                "schedule": {"type": "interval", "hours": 2},
            },
            queue=[],
            runtime={"status": "idle", "last_error": ""},
            history=[{"success": True}],
            diagnostics_snapshot={
                "summary_text": "24시간 3건 / 실패 0건 / 최근 cli",
                "status": "healthy",
                "warning_text": "",
            },
        )

        self.assertEqual(snapshot["schedule_summary"], "2시간마다 반복")
        self.assertEqual(snapshot["diagnostics_summary"], "24시간 3건 / 실패 0건 / 최근 cli")
        self.assertIn("작업 큐", snapshot["next_actions"][0])


if __name__ == "__main__":
    unittest.main()
