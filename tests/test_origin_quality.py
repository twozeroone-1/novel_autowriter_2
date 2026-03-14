import unittest

from core.origin_quality import validate_origin_draft


class TestOriginQuality(unittest.TestCase):
    def test_validate_origin_draft_rejects_missing_episode_number(self):
        report = validate_origin_draft(title="프롤로그", content="충분히 긴 본문입니다." * 20)

        self.assertEqual(report["status"], "failed")
        self.assertTrue(any("episode number" in error for error in report["errors"]))

    def test_validate_origin_draft_rejects_too_short_content(self):
        report = validate_origin_draft(title="1화. 시작", content="짧다")

        self.assertEqual(report["status"], "failed")
        self.assertTrue(any("too short" in error for error in report["errors"]))

    def test_validate_origin_draft_rejects_repeated_line_spam(self):
        report = validate_origin_draft(
            title="2화. 반복",
            content="\n".join(["같은 문장"] * 6),
        )

        self.assertEqual(report["status"], "failed")
        self.assertTrue(any("repeated lines" in error for error in report["errors"]))

    def test_validate_origin_draft_passes_for_well_formed_episode(self):
        report = validate_origin_draft(
            title="3화. 전개",
            content=("첫 문단입니다.\n둘째 문단입니다.\n셋째 문단입니다.\n넷째 문단입니다.\n" * 20),
        )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()
