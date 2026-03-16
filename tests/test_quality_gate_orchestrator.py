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
    def test_evaluate_quality_gate_returns_publishable_when_rules_and_structure_pass(self):
        result = evaluate_quality_gate(_valid_source())

        self.assertEqual(result["status"], "publishable")
        self.assertFalse(result["attempted_repair"])
        self.assertEqual(result["final_source"]["title"], "12화. 계약의 대가")

    @patch("core.quality_gate_orchestrator.repair_publish_source")
    def test_evaluate_quality_gate_repairs_retry_possible_source_once(self, repair_publish_source):
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


if __name__ == "__main__":
    unittest.main()
