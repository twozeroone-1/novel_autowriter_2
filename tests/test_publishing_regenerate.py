import unittest
from unittest.mock import patch


class TestPublishingRegenerate(unittest.TestCase):
    @patch("core.publishing_regenerate.generate_text")
    def test_regenerate_publish_source_reuses_same_episode_plan(self, generate_text):
        from core.publishing_regenerate import regenerate_publish_source

        generate_text.return_value = """
        {
          "title": "12화. 계약의 대가",
          "content": "# 12화. 계약의 대가\\n\\n재생성된 본문",
          "regeneration_summary": "critic blocked draft regenerated once"
        }
        """

        episode_plan = {"episode_objective": "계약 후폭풍을 수습한다", "target_length": 5000}
        result = regenerate_publish_source(
            {"title": "12화. 계약의 대가", "content": "# 12화. 계약의 대가\n\n초안"},
            episode_plan=episode_plan,
            project_name="sample",
            length_goal=5000,
        )

        self.assertEqual(result["status"], "applied")
        self.assertEqual(result["title"], "12화. 계약의 대가")
        self.assertIn("재생성된 본문", result["content"])
        self.assertIn("계약 후폭풍을 수습한다", generate_text.call_args.args[0])

    @patch("core.publishing_regenerate.generate_text")
    def test_regenerate_publish_source_normalizes_invalid_json_to_failure_payload(self, generate_text):
        from core.publishing_regenerate import regenerate_publish_source

        generate_text.return_value = "not json"

        result = regenerate_publish_source(
            {"title": "12화. 계약의 대가", "content": "# 12화. 계약의 대가\n\n초안"},
            episode_plan={"episode_objective": "계약 후폭풍을 수습한다"},
            project_name="sample",
        )

        self.assertEqual(result["status"], "failed")
        self.assertIn("invalid json", result["reason"])


if __name__ == "__main__":
    unittest.main()
