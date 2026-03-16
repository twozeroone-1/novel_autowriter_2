import sys
import types
import unittest
from pathlib import Path
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
    streamlit_stub.columns = lambda n: [types.SimpleNamespace(__enter__=lambda self: None, __exit__=lambda self, exc_type, exc, tb: False) for _ in range(n)]
    streamlit_stub.code = lambda *args, **kwargs: None
    sys.modules["streamlit"] = streamlit_stub

if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: None
    dotenv_stub.dotenv_values = lambda *args, **kwargs: {}
    sys.modules["dotenv"] = dotenv_stub


from ui.episode_workflow import build_episode_workflow_snapshot, render_episode_workflow


class TestEpisodeWorkflow(unittest.TestCase):
    def test_snapshot_uses_latest_manifest_episode_for_draft_summary(self):
        snapshot = build_episode_workflow_snapshot(
            manifest={
                "episodes": {
                    "ep_001": {"episode_id": "ep_001", "sequence": 1, "title": "1화. 시작", "status": "draft"},
                    "ep_012": {"episode_id": "ep_012", "sequence": 12, "title": "12화. 계약의 대가", "status": "publishable"},
                }
            },
            latest_episode_content="",
            latest_episode_plan={},
            latest_quality_report={},
            latest_packager_report={},
            publishing_queue=[],
            publishing_history=[],
        )

        self.assertEqual(snapshot["episode"]["episode_id"], "ep_012")
        self.assertEqual(snapshot["episode"]["status"], "publishable")
        self.assertEqual(snapshot["steps"][1]["state"], "완료")

    def test_snapshot_marks_quality_and_package_steps_done_for_publishable_packaged_episode(self):
        snapshot = build_episode_workflow_snapshot(
            manifest={
                "episodes": {
                    "ep_012": {"episode_id": "ep_012", "sequence": 12, "title": "12화. 계약의 대가", "status": "publishable"}
                }
            },
            latest_episode_content="# 12화. 계약의 대가\n\n첫 문단입니다.\n둘째 문단입니다.",
            latest_episode_plan={
                "episode_objective": "계약 후폭풍을 수습한다",
                "must_include_characters": ["하준", "채린"],
                "forbidden_moves": ["뜬금없는 세계관 확장"],
                "target_length": 5000,
            },
            latest_quality_report={
                "status": "publishable",
                "attempted_repair": True,
                "attempted_regenerate": False,
                "gate_reports": {"final": {"critic": {"status": "passed"}}},
            },
            latest_packager_report={
                "packages": {
                    "munpia": {"work_id": "work-1"},
                    "novelpia": {"work_id": "work-2"},
                }
            },
            publishing_queue=[{"status": "pending"}],
            publishing_history=[],
        )

        self.assertEqual([step["state"] for step in snapshot["steps"]], ["완료", "완료", "완료", "완료"])
        self.assertIn("repair 1회 적용", snapshot["quality_summary"])
        self.assertIn("문피아, 노벨피아", snapshot["packager_summary"])
        self.assertEqual(snapshot["critic_status"], "passed")
        self.assertTrue(snapshot["repair_applied"])
        self.assertFalse(snapshot["regenerate_applied"])
        self.assertIn("첫 문단입니다.", snapshot["draft_preview"])

    def test_snapshot_blocks_on_hard_fail_quality_and_recommends_fixing_quality_first(self):
        snapshot = build_episode_workflow_snapshot(
            manifest={
                "episodes": {
                    "ep_013": {"episode_id": "ep_013", "sequence": 13, "title": "13화. 균열", "status": "draft"}
                }
            },
            latest_episode_content="",
            latest_episode_plan={
                "episode_objective": "균열의 원인을 추적한다",
                "must_include_characters": ["하준"],
                "forbidden_moves": [],
                "target_length": 4800,
            },
            latest_quality_report={
                "status": "hard_fail",
                "errors": ["episode objective missing", "critic blocked"],
                "gate_reports": {"final": {"critic": {"status": "blocked"}}},
            },
            latest_packager_report={},
            publishing_queue=[],
            publishing_history=[],
        )

        self.assertEqual(snapshot["steps"][2]["state"], "차단")
        self.assertEqual(snapshot["steps"][3]["state"], "대기")
        self.assertEqual(snapshot["next_actions"][0], "고급: 원고 검수에서 품질 차단 사유를 먼저 해결하세요.")
        self.assertEqual(snapshot["shortcut_actions"][0]["label"], "고급: 원고 검수 열기")

    def test_snapshot_surfaces_draft_preview_path_and_queue_linkage_for_latest_episode(self):
        snapshot = build_episode_workflow_snapshot(
            manifest={
                "episodes": {
                    "ep_014": {
                        "episode_id": "ep_014",
                        "sequence": 14,
                        "title": "14화. 후속 조치",
                        "status": "publishable",
                        "draft_path": "episodes/drafts/ep_014.md",
                    }
                }
            },
            latest_episode_content="# 14화. 후속 조치\n\n후속 조치 본문 첫 문장입니다.\n다음 문장입니다.",
            latest_episode_plan={"episode_objective": "후속 조치를 마무리한다"},
            latest_quality_report={
                "status": "publishable",
                "attempted_repair": False,
                "attempted_regenerate": True,
                "gate_reports": {"final": {"critic": {"status": "passed"}}},
            },
            latest_packager_report={
                "packages": {"novelpia": {"work_id": "work-1"}}
            },
            publishing_queue=[
                {
                    "id": "pub-14",
                    "episode_id": "ep_014",
                    "title": "14화. 후속 조치",
                    "status": "pending",
                    "targets": {"novelpia": {"selected": True, "status": "pending"}},
                }
            ],
            publishing_history=[],
        )

        self.assertEqual(snapshot["draft_path"], "episodes/drafts/ep_014.md")
        self.assertIn("후속 조치 본문 첫 문장입니다.", snapshot["draft_preview"])
        self.assertEqual(snapshot["critic_status"], "passed")
        self.assertFalse(snapshot["repair_applied"])
        self.assertTrue(snapshot["regenerate_applied"])
        self.assertTrue(snapshot["queue_linked"])
        self.assertIn("노벨피아", snapshot["queue_link_summary"])
        self.assertEqual(snapshot["shortcut_actions"][0]["label"], "발행 운영 열기")

    def test_snapshot_recommends_generation_shortcut_when_no_latest_episode_exists(self):
        snapshot = build_episode_workflow_snapshot(
            manifest={"episodes": {}},
            latest_episode_content="",
            latest_episode_plan={},
            latest_quality_report={},
            latest_packager_report={},
            publishing_queue=[],
            publishing_history=[],
        )

        self.assertEqual(snapshot["next_actions"][0], "고급: 회차 생성에서 새 초안을 만들고 저장하세요.")
        self.assertEqual(snapshot["shortcut_actions"][0]["label"], "고급: 회차 생성 열기")
        self.assertEqual(snapshot["shortcut_actions"][0]["target_tab"], "고급: 회차 생성")

    def test_render_episode_workflow_triggers_navigation_callback_from_shortcut_button(self):
        class FakeColumn:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeStreamlit:
            def __init__(self):
                self.session_state = {}

            def header(self, *args, **kwargs):
                return None

            def caption(self, *args, **kwargs):
                return None

            def markdown(self, *args, **kwargs):
                return None

            def divider(self, *args, **kwargs):
                return None

            def subheader(self, *args, **kwargs):
                return None

            def columns(self, count, *args, **kwargs):
                if isinstance(count, (list, tuple)):
                    count = len(count)
                return [FakeColumn() for _ in range(count)]

            def button(self, label, *args, **kwargs):
                return label == "발행 운영 열기"

            def expander(self, *args, **kwargs):
                return FakeColumn()

            def code(self, *args, **kwargs):
                return None

            def info(self, *args, **kwargs):
                return None

        app = types.SimpleNamespace(generator=types.SimpleNamespace(ctx=types.SimpleNamespace(project_name="sample")))
        context = {
            "manifest": {},
            "latest_episode_content": "",
            "latest_episode_plan": {},
            "latest_quality_report": {},
            "latest_packager_report": {},
            "publishing_queue": [],
            "publishing_history": [],
        }
        snapshot = {
            "steps": ({"label": "계획", "state": "완료", "summary": "ok"},),
            "summary_lines": ("요약",),
            "next_actions": ("다음",),
            "shortcut_actions": (
                {
                    "label": "발행 운영 열기",
                    "description": "발행 준비를 확인합니다.",
                    "target_tab": "발행 운영",
                    "target_subsection": None,
                },
            ),
            "draft_path": "",
            "draft_preview": "",
            "quality_summary": "",
            "critic_status": "",
            "repair_applied": False,
            "regenerate_applied": False,
            "queue_link_summary": "",
            "packager_summary": "",
            "episode_plan_preview": {},
            "quality_report_preview": {},
            "packager_report_preview": {},
        }
        calls = []

        with (
            patch("ui.episode_workflow.st", FakeStreamlit()),
            patch("ui.episode_workflow.load_episode_workflow_context", return_value=context),
            patch("ui.episode_workflow.build_episode_workflow_snapshot", return_value=snapshot),
        ):
            render_episode_workflow(
                app,
                navigate_to_tab=lambda tab, subsection=None: calls.append((tab, subsection)),
            )

        self.assertEqual(calls, [("발행 운영", None)])


if __name__ == "__main__":
    unittest.main()
