import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.token_budget import (
    build_workspace_budget_snapshot,
    estimate_generation_cost_report,
    find_latest_sample_chapter,
    get_budget_recommendations,
    get_field_stats,
)


class TestTokenBudget(unittest.TestCase):
    def test_get_field_stats_reports_statuses(self):
        config = {
            "worldview": "x" * 1500,
            "tone_and_manner": "",
            "continuity": "x" * 1000,
            "state": "x" * 800,
            "summary_of_previous": "x" * 2000,
        }

        stats = {row["key"]: row for row in get_field_stats(config)}

        self.assertEqual(stats["worldview"]["status"], "적정")
        self.assertEqual(stats["tone_and_manner"]["status"], "비어 있음")
        self.assertEqual(stats["continuity"]["status"], "주의")
        self.assertEqual(stats["state"]["status"], "과다")
        self.assertEqual(stats["summary_of_previous"]["status"], "과다")

    def test_get_budget_recommendations_warns_for_missing_state_and_long_fields(self):
        config = {
            "worldview": "x" * 1800,
            "tone_and_manner": "x" * 700,
            "continuity": "x" * 1000,
            "state": "",
            "summary_of_previous": "x" * 1400,
        }

        recommendations = get_budget_recommendations(config)

        self.assertTrue(any("STATE" in message for message in recommendations))
        self.assertTrue(any("STORY_BIBLE" in message for message in recommendations))
        self.assertTrue(any("STYLE_GUIDE" in message for message in recommendations))
        self.assertTrue(any("CONTINUITY" in message for message in recommendations))
        self.assertTrue(any("PREVIOUS_SUMMARY" in message for message in recommendations))

    def test_build_workspace_budget_snapshot_ignores_non_workspace_fields(self):
        snapshot = build_workspace_budget_snapshot(
            {
                "worldview": "world",
                "tone_and_manner": "style",
                "continuity": "rules",
                "state": "state",
                "summary_of_previous": "summary",
                "plot_outline": "should be ignored",
                "extra_field": 123,
            }
        )

        self.assertEqual(
            snapshot,
            {
                "worldview": "world",
                "tone_and_manner": "style",
                "continuity": "rules",
                "state": "state",
                "summary_of_previous": "summary",
            },
        )

    def test_find_latest_sample_chapter_skips_auxiliary_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            chapters_dir = Path(tmpdir)
            draft_path = chapters_dir / "1화.md"
            auxiliary_draft = chapters_dir / "1화_초안.md"
            auxiliary_review = chapters_dir / "1화_검토리포트.md"
            auxiliary_revised = chapters_dir / "1화_수정본.md"
            newer_chapter = chapters_dir / "2화.md"
            base_mtime = 1_700_000_000

            for index, path in enumerate(
                [draft_path, auxiliary_draft, auxiliary_review, auxiliary_revised, newer_chapter],
                start=1,
            ):
                path.write_text(path.stem, encoding="utf-8")
                os.utime(path, (base_mtime + index, base_mtime + index))

            latest = find_latest_sample_chapter(chapters_dir)

            self.assertEqual(latest, newer_chapter)

    def test_estimate_generation_cost_report_uses_sample_ratio_and_pricing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            chapters_dir = Path(tmpdir)
            sample_path = chapters_dir / "sample.md"
            sample_text = "a" * 100
            sample_path.write_text(sample_text, encoding="utf-8")

            fake_ctx = SimpleNamespace(build_generation_prompt=lambda *args, **kwargs: "p" * 200)
            fake_generator = SimpleNamespace(ctx=fake_ctx, chapters_dir=chapters_dir)

            with patch("core.token_budget.count_text_tokens", side_effect=[100, 20, 60]):
                report = estimate_generation_cost_report(
                    generator=fake_generator,
                    instruction="scene instruction",
                    target_length=5000,
                    include_plot=True,
                    plot_strength="strict",
                    model_name="gemini-2.5-flash",
                )

            self.assertEqual(report["prompt_tokens"], 100)
            self.assertEqual(report["system_tokens"], 20)
            self.assertEqual(report["input_tokens"], 120)
            self.assertEqual(report["sample_chars"], 100)
            self.assertEqual(report["sample_tokens"], 60)
            self.assertEqual(report["estimated_output_tokens"], 3000)
            self.assertIn("sample.md", report["output_ratio_source"])
            self.assertAlmostEqual(report["input_cost_usd"], 0.000036)
            self.assertAlmostEqual(report["output_cost_usd"], 0.0075)
            self.assertAlmostEqual(report["total_cost_usd"], 0.007536)


if __name__ == "__main__":
    unittest.main()
