import unittest

from core.publishing_structure import evaluate_publish_structure


def _valid_body(line_count: int = 80) -> str:
    return "\n".join(f"장면 {index}: 유효한 본문입니다." for index in range(line_count))


class TestPublishingStructure(unittest.TestCase):
    def test_evaluate_publish_structure_returns_pass_for_valid_episode(self):
        report = evaluate_publish_structure(
            {
                "title": "12화. 계약의 대가",
                "content": "# 12화. 계약의 대가\n\n" + _valid_body(),
                "path": "episodes/publishable/ep_012.md",
            }
        )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["signals"]["heading_present"])
        self.assertEqual(report["signals"]["title_episode_number"], 12)
        self.assertEqual(report["signals"]["heading_episode_number"], 12)

    def test_evaluate_publish_structure_returns_retry_possible_for_auxiliary_markers(self):
        report = evaluate_publish_structure(
            {
                "title": "12화. 계약의 대가",
                "content": "# 12화. 계약의 대가\n\n수정본 메모\n\n" + _valid_body(50),
            }
        )

        self.assertEqual(report["status"], "retry_possible")
        self.assertTrue(any("auxiliary marker" in item for item in report["errors"]))

    def test_evaluate_publish_structure_returns_hard_fail_for_episode_number_mismatch(self):
        report = evaluate_publish_structure(
            {
                "title": "12화. 계약의 대가",
                "content": "# 13화. 다른 번호\n\n" + _valid_body(),
            }
        )

        self.assertEqual(report["status"], "hard_fail")
        self.assertTrue(any("episode number mismatch" in item for item in report["errors"]))

    def test_evaluate_publish_structure_returns_retry_possible_for_repeated_line_spam(self):
        repeated = "같은 줄입니다.\n" * 8
        report = evaluate_publish_structure(
            {
                "title": "12화. 계약의 대가",
                "content": "# 12화. 계약의 대가\n\n" + repeated + "\n" + _valid_body(),
            }
        )

        self.assertEqual(report["status"], "retry_possible")
        self.assertGreater(report["signals"]["repeated_line_count"], 0)


if __name__ == "__main__":
    unittest.main()
