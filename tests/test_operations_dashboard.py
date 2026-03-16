import sys
import types
import unittest
from unittest.mock import patch


if "streamlit" not in sys.modules:
    streamlit_stub = types.ModuleType("streamlit")
    streamlit_stub.session_state = {}
    streamlit_stub.set_page_config = lambda *args, **kwargs: None

    def _cache_resource(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    streamlit_stub.cache_resource = _cache_resource
    streamlit_stub.info = lambda *args, **kwargs: None
    streamlit_stub.warning = lambda *args, **kwargs: None
    streamlit_stub.error = lambda *args, **kwargs: None
    streamlit_stub.caption = lambda *args, **kwargs: None
    streamlit_stub.metric = lambda *args, **kwargs: None
    streamlit_stub.subheader = lambda *args, **kwargs: None
    streamlit_stub.markdown = lambda *args, **kwargs: None
    streamlit_stub.divider = lambda *args, **kwargs: None
    streamlit_stub.button = lambda *args, **kwargs: False
    streamlit_stub.columns = lambda n: [types.SimpleNamespace(__enter__=lambda self: None, __exit__=lambda self, exc_type, exc, tb: False) for _ in range(n)]
    sys.modules["streamlit"] = streamlit_stub


from ui.operations_dashboard import build_operations_overview_snapshot


class TestOperationsDashboard(unittest.TestCase):
    def test_snapshot_marks_publishing_not_ready_when_enabled_platform_is_missing_credentials_and_work_mapping(self):
        snapshot = build_operations_overview_snapshot(
            project_name="sample",
            workspace_settings={
                "worldview": "world",
                "tone_and_manner": "style",
                "continuity": "rules",
                "state": "current state",
            },
            publishing_config={
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
            publishing_runtime={},
            publishing_queue=[],
            credential_loader=lambda _project, _platform: {"username": "", "password": ""},
        )

        self.assertFalse(snapshot["publishing_ready"])
        self.assertEqual(snapshot["ready_platform_count"], 0)
        self.assertEqual(snapshot["enabled_platform_count"], 1)

    def test_snapshot_blockers_include_missing_credentials_and_work_mapping(self):
        snapshot = build_operations_overview_snapshot(
            project_name="sample",
            workspace_settings={
                "worldview": "world",
                "tone_and_manner": "style",
                "continuity": "rules",
                "state": "state",
            },
            publishing_config={
                "enabled": True,
                "schedule": {"type": "daily", "time": "21:00"},
                "platforms": {
                    "novelpia": {
                        "enabled": True,
                        "work_id": "",
                        "upload_url_template": "",
                    }
                },
            },
            publishing_runtime={},
            publishing_queue=[],
            credential_loader=lambda _project, _platform: {"username": "", "password": ""},
        )

        self.assertIn("노벨피아 계정이 설정되지 않았습니다.", snapshot["blockers"])
        self.assertIn("노벨피아 work_id가 비어 있습니다.", snapshot["blockers"])
        self.assertIn("노벨피아 업로드 URL이 비어 있습니다.", snapshot["blockers"])

    def test_snapshot_recommends_configuration_work_before_queue_execution(self):
        snapshot = build_operations_overview_snapshot(
            project_name="sample",
            workspace_settings={
                "worldview": "world",
                "tone_and_manner": "style",
                "continuity": "rules",
                "state": "state",
            },
            publishing_config={
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
            publishing_runtime={"status": "idle", "last_error": ""},
            publishing_queue=[{"status": "pending"}],
            credential_loader=lambda _project, _platform: {"username": "", "password": ""},
        )

        self.assertGreaterEqual(len(snapshot["next_actions"]), 2)
        self.assertEqual(snapshot["next_actions"][0], "플랫폼 계정을 keyring 또는 env fallback으로 설정하세요.")
        self.assertEqual(snapshot["next_actions"][1], "플랫폼 작품 매핑(work_id / 업로드 URL)을 채우세요.")

    def test_snapshot_uses_shared_publishing_readiness_snapshot(self):
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

        with patch("ui.operations_dashboard.build_publishing_readiness_snapshot", return_value=shared_snapshot) as mocked_build:
            snapshot = build_operations_overview_snapshot(
                project_name="sample",
                workspace_settings={
                    "worldview": "world",
                    "tone_and_manner": "style",
                    "continuity": "rules",
                    "state": "state",
                },
                publishing_config={"enabled": True, "schedule": {"type": "daily", "time": "21:00"}, "platforms": {}},
                publishing_runtime={"status": "idle", "last_error": ""},
                publishing_queue=[],
                credential_loader=lambda _project, _platform: {"username": "", "password": ""},
            )

        mocked_build.assert_called_once()
        self.assertEqual(snapshot["platform_rows"], shared_snapshot["platform_rows"])
        self.assertIn("shared blocker", snapshot["blockers"])
        self.assertIn("shared action", snapshot["next_actions"])


if __name__ == "__main__":
    unittest.main()
