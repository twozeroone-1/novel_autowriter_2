import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.context as context_module
import core.run_snapshot_store as run_snapshot_store_module
from core.generator import Generator


def _empty_plan(*, target_length: int = 5000) -> dict:
    return {
        "episode_objective": "",
        "must_include_characters": [],
        "hooks_to_payoff": [],
        "hooks_to_advance": [],
        "forbidden_moves": [],
        "target_length": target_length,
        "tone_notes": "",
        "continuity_focus": [],
        "plan_version": "v1",
    }


class TestGeneratorPlanning(unittest.TestCase):
    def test_create_chapter_includes_episode_plan_block_when_planner_returns_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                generator = Generator(project_name="sample")
                with patch.object(
                    generator.episode_planner,
                    "build_episode_plan",
                    return_value={
                        "episode_objective": "탈출 후 은신처 확보",
                        "must_include_characters": ["lead"],
                        "hooks_to_payoff": [],
                        "hooks_to_advance": ["계약서 비밀"],
                        "forbidden_moves": ["새 설정 추가 금지"],
                        "target_length": 5000,
                        "tone_notes": "긴장 유지",
                        "continuity_focus": ["추격 직후 상태 유지"],
                        "plan_version": "v1",
                    },
                ), patch("core.generator.generate_text", return_value="chapter body") as mocked_generate:
                    generator.create_chapter("다음 화를 써줘", length_goal=5000)

                prompt = mocked_generate.call_args.args[0]
                self.assertIn("[EPISODE PLAN]", prompt)
                self.assertIn("탈출 후 은신처 확보", prompt)
                self.assertIn("계약서 비밀", prompt)

    def test_create_chapter_falls_back_when_planner_returns_empty_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                generator = Generator(project_name="sample")
                with patch.object(
                    generator.episode_planner,
                    "build_episode_plan",
                    return_value=_empty_plan(target_length=5000),
                ), patch("core.generator.generate_text", return_value="chapter body") as mocked_generate:
                    generator.create_chapter("다음 화를 써줘", length_goal=5000)

                prompt = mocked_generate.call_args.args[0]
                self.assertNotIn("[EPISODE PLAN]", prompt)

    def test_create_chapter_passes_plot_flag_into_episode_planner(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                generator = Generator(project_name="sample")
                with patch.object(
                    generator.episode_planner,
                    "build_episode_plan",
                    return_value=_empty_plan(target_length=4800),
                ) as build_episode_plan, patch("core.generator.generate_text", return_value="chapter body"):
                    generator.create_chapter(
                        "다음 화를 써줘",
                        length_goal=4800,
                        include_plot=True,
                        plot_strength="strict",
                    )

                build_episode_plan.assert_called_once_with(
                    "다음 화를 써줘",
                    length_goal=4800,
                    include_plot=True,
                    plot_strength="strict",
                )

    def test_create_chapter_writes_episode_plan_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            with patch.object(context_module, "BASE_DATA_DIR", base):
                with patch.object(run_snapshot_store_module, "DATA_PROJECTS_DIR", base):
                    generator = Generator(project_name="sample")
                    with patch.object(
                        generator.episode_planner,
                        "build_episode_plan",
                        return_value={
                            "episode_objective": "추적을 끊고 은신처 확보",
                            "must_include_characters": ["lead"],
                            "hooks_to_payoff": ["계약의 반동"],
                            "hooks_to_advance": ["계약서 비밀"],
                            "forbidden_moves": ["새 설정 추가 금지"],
                            "target_length": 5200,
                            "tone_notes": "긴장 유지",
                            "continuity_focus": ["도주 직후 상태 유지"],
                            "plan_version": "v1",
                        },
                    ), patch("core.generator.generate_text", return_value="chapter body"):
                        result = generator.create_chapter("다음 화를 써줘", length_goal=5200)

                    self.assertEqual(result, "chapter body")
                    run_dirs = list((base / "sample" / "runs").iterdir())
                    self.assertEqual(len(run_dirs), 1)
                    snapshot = json.loads((run_dirs[0] / "episode_plan.json").read_text(encoding="utf-8"))
                    self.assertEqual(snapshot["episode_objective"], "추적을 끊고 은신처 확보")
                    self.assertEqual(snapshot["target_length"], 5200)

    def test_create_chapter_writes_empty_plan_snapshot_when_planner_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            with patch.object(context_module, "BASE_DATA_DIR", base):
                with patch.object(run_snapshot_store_module, "DATA_PROJECTS_DIR", base):
                    generator = Generator(project_name="sample")
                    with patch.object(
                        generator.episode_planner,
                        "build_episode_plan",
                        side_effect=RuntimeError("planner exploded"),
                    ), patch("core.generator.generate_text", return_value="chapter body") as mocked_generate:
                        result = generator.create_chapter("다음 화를 써줘", length_goal=5100)

                    self.assertEqual(result, "chapter body")
                    prompt = mocked_generate.call_args.args[0]
                    self.assertNotIn("[EPISODE PLAN]", prompt)
                    run_dirs = list((base / "sample" / "runs").iterdir())
                    self.assertEqual(len(run_dirs), 1)
                    snapshot = json.loads((run_dirs[0] / "episode_plan.json").read_text(encoding="utf-8"))
                    self.assertEqual(snapshot["episode_objective"], "")
                    self.assertEqual(snapshot["target_length"], 5100)
                    self.assertEqual(snapshot["plan_version"], "v1")
                    self.assertIn("planner exploded", snapshot["planner_error"])


if __name__ == "__main__":
    unittest.main()
