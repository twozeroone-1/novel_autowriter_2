import importlib
import importlib.util
import sys
import types
import unittest
from unittest.mock import patch


def _install_fake_streamlit():
    fake_streamlit = types.SimpleNamespace(
        text_area=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        caption=lambda *args, **kwargs: None,
        selectbox=lambda *args, **kwargs: "all",
        expander=lambda *args, **kwargs: None,
        divider=lambda *args, **kwargs: None,
        dataframe=lambda *args, **kwargs: None,
    )
    sys.modules["streamlit"] = fake_streamlit


class TestDiagnosticsUi(unittest.TestCase):
    def _load_module(self):
        spec = importlib.util.find_spec("ui.diagnostics")
        self.assertIsNotNone(spec, "ui.diagnostics should exist")
        _install_fake_streamlit()
        sys.modules.pop("ui.diagnostics", None)
        return importlib.import_module("ui.diagnostics")

    def test_format_sidebar_summary_uses_korean_compact_metadata(self):
        diagnostics_ui = self._load_module()
        summary = diagnostics_ui.format_sidebar_summary(
            {"run_count": 3, "failure_count": 1, "latest_backend": "cli"}
        )

        self.assertIn("24시간", summary)
        self.assertIn("3건", summary)
        self.assertIn("실패 1건", summary)
        self.assertIn("cli", summary)

    def test_filter_runs_by_success_backend_and_model(self):
        diagnostics_ui = self._load_module()
        runs = [
            {
                "success": False,
                "requested_backend": "auto",
                "actual_backend": "api",
                "model": "gemini-2.5-flash",
            },
            {
                "success": True,
                "requested_backend": "api",
                "actual_backend": "api",
                "model": "gemini-2.5-pro",
            },
        ]

        filtered = diagnostics_ui.filter_runs(
            runs,
            success_filter="failed",
            requested_backend="auto",
            actual_backend="api",
            model_name="gemini-2.5-flash",
        )

        self.assertEqual(len(filtered), 1)

    def test_build_detail_rows_preserves_newest_first_metadata(self):
        diagnostics_ui = self._load_module()
        rows = diagnostics_ui.build_detail_rows(
            [
                {
                    "timestamp": "2026-03-11T12:00:00+00:00",
                    "feature": "review",
                    "success": False,
                    "requested_backend": "auto",
                    "actual_backend": "api",
                    "model": "gemini-2.5-flash",
                    "duration_ms": 2100,
                    "prompt_text": "prompt",
                    "response_text": "",
                    "stderr_text": "",
                    "error_text": "api failed",
                    "fallback_note": "cli failed -> api",
                }
            ]
        )

        self.assertEqual(rows[0]["feature"], "review")
        self.assertEqual(rows[0]["status"], "failed")
        self.assertEqual(rows[0]["error_text"], "api failed")

    def test_get_diagnostics_warning_text_is_korean(self):
        diagnostics_ui = self._load_module()
        warning_text = diagnostics_ui.get_diagnostics_warning_text()

        self.assertIn("민감", warning_text)
        self.assertIn("프롬프트", warning_text)

    def test_render_detail_fields_uses_read_only_text_areas(self):
        diagnostics_ui = self._load_module()
        row = {
            "prompt_text": "prompt",
            "response_text": "response",
            "stderr_text": "stderr",
            "error_text": "error",
            "fallback_note": "fallback",
        }

        with patch.object(diagnostics_ui.st, "text_area") as mocked_text_area:
            diagnostics_ui.render_detail_fields(row, index=0)

        self.assertEqual(mocked_text_area.call_count, 5)
        labels = [call.args[0] for call in mocked_text_area.call_args_list]
        self.assertEqual(labels, ["프롬프트", "응답", "stderr", "오류", "fallback 메모"])
        self.assertTrue(all(call.kwargs["disabled"] for call in mocked_text_area.call_args_list))


    def test_build_automation_history_rows_formats_execution_metadata(self):
        diagnostics_ui = self._load_module()
        rows = diagnostics_ui.build_automation_history_rows(
            [
                {
                    "timestamp": "2026-03-12T09:18:10.284288+09:00",
                    "title": "8화",
                    "success": True,
                    "saved_path": "C:/novel/8화.md",
                    "context_update": {
                        "legacy": {"status": "skipped"},
                        "canon_candidate": {"status": "recorded"},
                    },
                },
                {
                    "timestamp": "2026-03-12T06:42:28.396475+09:00",
                    "title": "7화",
                    "success": False,
                    "error_text": "boom",
                    "context_update": {
                        "legacy": {"status": "partial_failure"},
                        "canon_candidate": {"status": "missing"},
                    },
                },
            ]
        )

        self.assertEqual(rows[0]["timestamp"], "2026-03-12T09:18:10.284288+09:00")
        self.assertEqual(rows[0]["title"], "8화")
        self.assertEqual(rows[0]["result"], "success")
        self.assertEqual(rows[0]["context_update"], "legacy: skipped / canon: recorded")
        self.assertEqual(rows[0]["detail"], "C:/novel/8화.md")
        self.assertEqual(rows[1]["result"], "failed")
        self.assertEqual(rows[1]["context_update"], "legacy: partial_failure / canon: missing")
        self.assertEqual(rows[1]["detail"], "boom")


if __name__ == "__main__":
    unittest.main()
