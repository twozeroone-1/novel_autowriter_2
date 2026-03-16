import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.canon_store as canon_store_module
import core.context_state_store as context_state_store_module
import core.plot_store as plot_store_module
import core.publishing_store as publishing_store_module
import core.release_policy_store as release_policy_store_module
import core.story_bible_store as story_bible_store_module
from core.canon_store import CanonStore
from core.context_state_store import ContextStateStore
from core.episode_planner import EpisodePlanner
from core.plot_store import PlotStore
from core.publishing_store import PublishingStore
from core.release_policy_store import ReleasePolicyStore
from core.story_bible_store import StoryBibleStore


class TestEpisodePlanner(unittest.TestCase):
    def _patch_store_dirs(self, base: Path):
        return patch.multiple(
            story_bible_store_module,
            DATA_PROJECTS_DIR=base,
        ), patch.multiple(
            canon_store_module,
            DATA_PROJECTS_DIR=base,
        ), patch.multiple(
            context_state_store_module,
            DATA_PROJECTS_DIR=base,
        ), patch.multiple(
            plot_store_module,
            DATA_PROJECTS_DIR=base,
        ), patch.multiple(
            release_policy_store_module,
            DATA_PROJECTS_DIR=base,
        ), patch.multiple(
            publishing_store_module,
            DATA_PROJECTS_DIR=base,
        )

    def _seed_structured_inputs(self, base: Path) -> None:
        StoryBibleStore("sample").save(
            {
                "worldview": "도시 판타지",
                "style_guide": "긴장 유지",
                "fixed_rules": "설정 충돌 금지",
                "author_intent": "",
                "forbidden_elements": "",
            }
        )
        CanonStore("sample").save_current_state(
            {
                "people": {"lead": {"goal": "도주"}},
                "resources": {"cash": 1000},
                "hooks": ["계약서 비밀"],
                "timeline": ["ep_011"],
            }
        )
        ContextStateStore("sample").save(
            {
                "state": "추격 직후",
                "summary_of_previous": "주인공이 계약서를 훔쳤다.",
            }
        )
        ReleasePolicyStore("sample").save(
            {
                "global": {"max_daily_releases": 1, "burst_allowed": False},
                "platforms": {"munpia": {"enabled": True}},
            }
        )
        PublishingStore("sample").append_history(
            {
                "timestamp": "2026-03-16T00:00:00+00:00",
                "success": True,
                "job_id": "pub1",
            }
        )

    def test_build_episode_plan_passes_project_and_feature_to_generate_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            patches = self._patch_store_dirs(base)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                self._seed_structured_inputs(base)
                planner = EpisodePlanner(project_name="sample")
                with patch(
                    "core.episode_planner.generate_text",
                    return_value=(
                        '{"episode_objective":"추적을 피하고 단서를 확보","must_include_characters":["lead"],'
                        '"hooks_to_payoff":[],"hooks_to_advance":["계약서 비밀"],'
                        '"forbidden_moves":["새 설정 추가 금지"],"target_length":5000,'
                        '"tone_notes":"긴장 유지","continuity_focus":["도주 직후 상태 유지"],"plan_version":"v1"}'
                    ),
                ) as mocked_generate:
                    result = planner.build_episode_plan("다음 화를 써줘", length_goal=5000, include_plot=False)

                self.assertEqual(result["plan_version"], "v1")
                self.assertEqual(result["episode_objective"], "추적을 피하고 단서를 확보")
                self.assertEqual(mocked_generate.call_args.kwargs["feature"], "episode_plan")
                self.assertEqual(mocked_generate.call_args.kwargs["project_name"], "sample")

    def test_build_episode_plan_normalizes_missing_fields_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            patches = self._patch_store_dirs(base)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                self._seed_structured_inputs(base)
                planner = EpisodePlanner(project_name="sample")
                with patch(
                    "core.episode_planner.generate_text",
                    return_value='{"episode_objective":"은신처 확보"}',
                ):
                    result = planner.build_episode_plan("다음 화를 써줘", length_goal=4300, include_plot=False)

                self.assertEqual(result["episode_objective"], "은신처 확보")
                self.assertEqual(result["must_include_characters"], [])
                self.assertEqual(result["hooks_to_payoff"], [])
                self.assertEqual(result["hooks_to_advance"], [])
                self.assertEqual(result["forbidden_moves"], [])
                self.assertEqual(result["target_length"], 4300)
                self.assertEqual(result["tone_notes"], "")
                self.assertEqual(result["continuity_focus"], [])
                self.assertEqual(result["plan_version"], "v1")

    def test_build_episode_plan_omits_plot_input_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            patches = self._patch_store_dirs(base)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                self._seed_structured_inputs(base)
                PlotStore("sample").save({"plot_outline": "숨겨진 음모", "plot_version": "1"})
                planner = EpisodePlanner(project_name="sample")
                with patch(
                    "core.episode_planner.generate_text",
                    return_value='{"episode_objective":"은신처 확보"}',
                ) as mocked_generate:
                    planner.build_episode_plan("다음 화를 써줘", length_goal=5000, include_plot=False)

                prompt = mocked_generate.call_args.args[0]
                self.assertNotIn("숨겨진 음모", prompt)
                self.assertNotIn("[PLOT OUTLINE]", prompt)

    def test_build_episode_plan_uses_empty_plan_when_model_output_is_not_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            patches = self._patch_store_dirs(base)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                self._seed_structured_inputs(base)
                planner = EpisodePlanner(project_name="sample")
                with patch("core.episode_planner.generate_text", return_value="not json"):
                    result = planner.build_episode_plan("다음 화를 써줘", length_goal=3900, include_plot=False)

                self.assertEqual(result["episode_objective"], "")
                self.assertEqual(result["must_include_characters"], [])
                self.assertEqual(result["hooks_to_payoff"], [])
                self.assertEqual(result["hooks_to_advance"], [])
                self.assertEqual(result["forbidden_moves"], [])
                self.assertEqual(result["target_length"], 3900)
                self.assertEqual(result["tone_notes"], "")
                self.assertEqual(result["continuity_focus"], [])
                self.assertEqual(result["plan_version"], "v1")


if __name__ == "__main__":
    unittest.main()
