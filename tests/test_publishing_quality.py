import importlib
import importlib.util
import unittest


class TestPublishingQuality(unittest.TestCase):
    def _load_evaluator(self):
        spec = importlib.util.find_spec("core.publishing_quality")
        self.assertIsNotNone(spec, "core.publishing_quality should exist")
        module = importlib.import_module("core.publishing_quality")
        evaluator = getattr(module, "evaluate_publish_source", None)
        self.assertIsNotNone(evaluator, "evaluate_publish_source should exist")
        return evaluator

    def test_evaluate_publish_source_returns_hard_fail_for_invalid_title_and_short_body(self):
        evaluate_publish_source = self._load_evaluator()

        report = evaluate_publish_source({"title": "프롤로그", "content": "짧다"})

        self.assertEqual(report["status"], "hard_fail")
        self.assertGreaterEqual(len(report["errors"]), 1)

    def test_evaluate_publish_source_returns_hard_fail_for_blocked_markers(self):
        evaluate_publish_source = self._load_evaluator()

        report = evaluate_publish_source({"title": "1화", "content": "검수리포트 초안"})

        self.assertEqual(report["status"], "hard_fail")
        self.assertTrue(any("blocked marker" in item for item in report["errors"]))

    def test_evaluate_publish_source_returns_publishable_for_valid_source(self):
        evaluate_publish_source = self._load_evaluator()

        report = evaluate_publish_source(
            {
                "title": "12화. 계약의 대가",
                "content": "유효한 본문 " * 80,
            }
        )

        self.assertEqual(report["status"], "publishable")
        self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()
