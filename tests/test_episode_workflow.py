import sys
import types
import unittest


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


from ui.episode_workflow import build_episode_workflow_snapshot


class TestEpisodeWorkflow(unittest.TestCase):
    def test_snapshot_uses_latest_manifest_episode_for_draft_summary(self):
        snapshot = build_episode_workflow_snapshot(
            manifest={
                "episodes": {
                    "ep_001": {"episode_id": "ep_001", "sequence": 1, "title": "1화. 시작", "status": "draft"},
                    "ep_012": {"episode_id": "ep_012", "sequence": 12, "title": "12화. 계약의 대가", "status": "publishable"},
                }
            },
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

    def test_snapshot_blocks_on_hard_fail_quality_and_recommends_fixing_quality_first(self):
        snapshot = build_episode_workflow_snapshot(
            manifest={
                "episodes": {
                    "ep_013": {"episode_id": "ep_013", "sequence": 13, "title": "13화. 균열", "status": "draft"}
                }
            },
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
        self.assertEqual(snapshot["next_actions"][0], "원고 검수 또는 회차 생성에서 품질 차단 사유를 먼저 해결하세요.")


if __name__ == "__main__":
    unittest.main()
