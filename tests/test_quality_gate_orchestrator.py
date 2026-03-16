import unittest
from unittest.mock import patch

from core.quality_gate_orchestrator import evaluate_quality_gate


def _valid_source(*, title: str = "12화. 계약의 대가", content: str | None = None) -> dict:
    body = content or "\n".join(f"정상 본문 {index}입니다." for index in range(80))
    return {
        "title": title,
        "content": body if body.startswith("#") else f"# {title}\n\n{body}",
        "path": "episodes/publishable/ep_012.md",
        "episode_id": "ep_012",
    }


class TestQualityGateOrchestrator(unittest.TestCase):
    @patch("core.quality_gate_orchestrator.evaluate_publish_critic")
    def test_evaluate_quality_gate_calls_critic_only_after_cheap_gates_pass(self, evaluate_publish_critic):
        evaluate_publish_critic.return_value = {
            "status": "passed",
            "summary": "ok",
            "issues": [],
            "model": "gemini-2.5-flash",
            "cost": {"mode": "single_pass"},
            "raw_excerpt": "",
        }

        result = evaluate_quality_gate(
            _valid_source(),
            episode_plan={"episode_objective": "계약의 대가를 수습한다"},
            regenerate_enabled=False,
        )

        self.assertEqual(result["status"], "publishable")
        evaluate_publish_critic.assert_called_once()

    @patch("core.quality_gate_orchestrator.evaluate_publish_critic")
    def test_evaluate_quality_gate_returns_publishable_when_rules_and_structure_pass(self, evaluate_publish_critic):
        evaluate_publish_critic.return_value = {
            "status": "passed",
            "summary": "ok",
            "issues": [],
            "model": "gemini-2.5-flash",
            "cost": {"mode": "single_pass"},
            "raw_excerpt": "",
        }

        result = evaluate_quality_gate(_valid_source(), regenerate_enabled=False)

        self.assertEqual(result["status"], "publishable")
        self.assertFalse(result["attempted_repair"])
        self.assertEqual(result["final_source"]["title"], "12화. 계약의 대가")

    @patch("core.quality_gate_orchestrator.repair_publish_source")
    @patch("core.quality_gate_orchestrator.evaluate_publish_critic")
    def test_evaluate_quality_gate_repairs_retry_possible_source_once(
        self,
        evaluate_publish_critic,
        repair_publish_source,
    ):
        evaluate_publish_critic.return_value = {
            "status": "passed",
            "summary": "ok",
            "issues": [],
            "model": "gemini-2.5-flash",
            "cost": {"mode": "single_pass"},
            "raw_excerpt": "",
        }
        repair_publish_source.return_value = {
            "title": "12화. 계약의 대가",
            "content": "# 12화. 계약의 대가\n\n"
            + "\n".join(f"정리된 본문 {index}입니다." for index in range(80)),
        }

        result = evaluate_quality_gate(
            _valid_source(
                content="# 12화. 계약의 대가\n\n수정본 메모\n\n"
                + "\n".join(f"정리 전 본문 {index}입니다." for index in range(50))
            )
        )

        self.assertEqual(result["status"], "publishable")
        self.assertTrue(result["attempted_repair"])
        repair_publish_source.assert_called_once()

    @patch("core.quality_gate_orchestrator.repair_publish_source")
    def test_evaluate_quality_gate_hard_fails_when_repair_still_fails(self, repair_publish_source):
        repair_publish_source.return_value = {
            "title": "12화. 계약의 대가",
            "content": "# 13화. 번호 불일치\n\n여전히 문제 있음\n",
        }

        result = evaluate_quality_gate(
            _valid_source(
                content="# 12화. 계약의 대가\n\n수정본 메모\n\n"
                + "\n".join(f"정리 전 본문 {index}입니다." for index in range(50))
            )
        )

        self.assertEqual(result["status"], "hard_fail")
        self.assertTrue(result["attempted_repair"])
        repair_publish_source.assert_called_once()

    @patch("core.quality_gate_orchestrator.repair_publish_source")
    def test_evaluate_quality_gate_skips_repair_for_immediate_hard_fail(self, repair_publish_source):
        result = evaluate_quality_gate(
            _valid_source(content="# 99화. 완전히 다른 번호\n\n짧음")
        )

        self.assertEqual(result["status"], "hard_fail")
        self.assertFalse(result["attempted_repair"])
        repair_publish_source.assert_not_called()

    @patch("core.quality_gate_orchestrator.evaluate_publish_critic")
    def test_evaluate_quality_gate_hard_fails_when_critic_blocks(self, evaluate_publish_critic):
        evaluate_publish_critic.return_value = {
            "status": "blocked",
            "summary": "objective drift",
            "issues": ["episode objective missing"],
            "model": "gemini-2.5-flash",
            "cost": {"mode": "single_pass"},
            "raw_excerpt": "",
        }

        result = evaluate_quality_gate(
            _valid_source(),
            episode_plan={"episode_objective": "계약의 대가를 수습한다"},
            regenerate_enabled=False,
        )

        self.assertEqual(result["status"], "hard_fail")
        self.assertIn("episode objective missing", result["errors"])
        self.assertEqual(result["gate_reports"]["final"]["critic"]["status"], "blocked")

    @patch("core.quality_gate_orchestrator.evaluate_publish_critic")
    def test_evaluate_quality_gate_hard_fails_when_critic_is_unavailable(self, evaluate_publish_critic):
        evaluate_publish_critic.return_value = {
            "status": "critic_unavailable",
            "summary": "backend unavailable",
            "issues": [],
            "model": "gemini-2.5-flash",
            "cost": {"mode": "single_pass"},
            "raw_excerpt": "",
        }

        result = evaluate_quality_gate(_valid_source(), regenerate_enabled=False)

        self.assertEqual(result["status"], "hard_fail")
        self.assertIn("backend unavailable", result["errors"])
        self.assertEqual(result["gate_reports"]["final"]["critic"]["status"], "critic_unavailable")

    @patch("core.quality_gate_orchestrator.evaluate_publish_critic")
    def test_evaluate_quality_gate_does_not_call_critic_on_initial_hard_fail(self, evaluate_publish_critic):
        result = evaluate_quality_gate(
            _valid_source(content="# 99화. 완전히 다른 번호\n\n짧음")
        )

        self.assertEqual(result["status"], "hard_fail")
        evaluate_publish_critic.assert_not_called()

    @patch("core.quality_gate_orchestrator.regenerate_publish_source")
    @patch("core.quality_gate_orchestrator.evaluate_publish_critic")
    def test_evaluate_quality_gate_regenerates_once_when_critic_blocks(
        self,
        evaluate_publish_critic,
        regenerate_publish_source,
    ):
        evaluate_publish_critic.side_effect = [
            {
                "status": "blocked",
                "summary": "objective drift",
                "issues": ["episode objective missing"],
                "model": "gemini-2.5-flash",
                "cost": {"mode": "single_pass"},
                "raw_excerpt": "",
            },
            {
                "status": "passed",
                "summary": "ok",
                "issues": [],
                "model": "gemini-2.5-flash",
                "cost": {"mode": "single_pass"},
                "raw_excerpt": "",
            },
        ]
        regenerate_publish_source.return_value = {
            "status": "applied",
            "reason": "",
            "title": "12화. 계약의 대가",
            "content": "# 12화. 계약의 대가\n\n" + "\n".join(f"재생성 본문 {index}" for index in range(80)),
            "regeneration_summary": "critic-blocked draft regenerated",
        }

        result = evaluate_quality_gate(
            _valid_source(),
            episode_plan={"episode_objective": "계약 후폭풍 수습"},
        )

        self.assertEqual(result["status"], "publishable")
        self.assertTrue(result["attempted_regenerate"])
        regenerate_publish_source.assert_called_once()

    @patch("core.quality_gate_orchestrator.regenerate_publish_source")
    def test_evaluate_quality_gate_does_not_regenerate_non_regenerateable_hard_fail(self, regenerate_publish_source):
        result = evaluate_quality_gate(
            _valid_source(content="# 99화. 완전히 다른 번호\n\n짧음")
        )

        self.assertEqual(result["status"], "hard_fail")
        regenerate_publish_source.assert_not_called()

    @patch("core.quality_gate_orchestrator.regenerate_publish_source")
    @patch("core.quality_gate_orchestrator.evaluate_publish_critic")
    def test_evaluate_quality_gate_hard_fails_when_regenerated_source_still_fails(
        self,
        evaluate_publish_critic,
        regenerate_publish_source,
    ):
        evaluate_publish_critic.return_value = {
            "status": "blocked",
            "summary": "objective drift",
            "issues": ["episode objective missing"],
            "model": "gemini-2.5-flash",
            "cost": {"mode": "single_pass"},
            "raw_excerpt": "",
        }
        regenerate_publish_source.return_value = {
            "status": "applied",
            "reason": "",
            "title": "12화. 계약의 대가",
            "content": "# 12화. 계약의 대가\n\n재생성했지만 여전히 문제가 있는 본문",
            "regeneration_summary": "still weak",
        }

        result = evaluate_quality_gate(
            _valid_source(),
            episode_plan={"episode_objective": "계약 후폭풍 수습"},
        )

        self.assertEqual(result["status"], "hard_fail")
        self.assertTrue(result["attempted_regenerate"])
        regenerate_publish_source.assert_called_once()


if __name__ == "__main__":
    unittest.main()
