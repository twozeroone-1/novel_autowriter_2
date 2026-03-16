import importlib
import importlib.util
import unittest
from unittest.mock import patch

from core.llm import LLMError


def _valid_source() -> dict:
    return {
        "title": "12화. 계약의 대가",
        "content": "# 12화. 계약의 대가\n\n" + "\n".join(f"정상 본문 {index}입니다." for index in range(80)),
        "episode_id": "ep_012",
    }


class TestPublishingCritic(unittest.TestCase):
    def _load_module(self):
        spec = importlib.util.find_spec("core.publishing_critic")
        self.assertIsNotNone(spec, "core.publishing_critic should exist")
        return importlib.import_module("core.publishing_critic")

    def test_evaluate_publish_critic_returns_passed_for_valid_json(self):
        module = self._load_module()
        with patch.object(
            module,
            "generate_text",
            return_value='{"status":"passed","summary":"publish ready","issues":[]}',
        ) as mocked_generate:
            result = module.evaluate_publish_critic(
                _valid_source(),
                episode_plan={"episode_objective": "계약 대가를 수습한다"},
            )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["issues"], [])
        self.assertEqual(mocked_generate.call_args.kwargs["feature"], "publish_critic")

    def test_evaluate_publish_critic_returns_blocked_for_explicit_block(self):
        module = self._load_module()
        with patch.object(
            module,
            "generate_text",
            return_value='{"status":"blocked","summary":"objective drift","issues":["episode objective missing"]}',
        ):
            result = module.evaluate_publish_critic(_valid_source())

        self.assertEqual(result["status"], "blocked")
        self.assertIn("episode objective missing", result["issues"])

    def test_evaluate_publish_critic_returns_unavailable_on_llm_error(self):
        module = self._load_module()
        with patch.object(module, "generate_text", side_effect=LLMError("backend unavailable")):
            result = module.evaluate_publish_critic(_valid_source())

        self.assertEqual(result["status"], "critic_unavailable")
        self.assertIn("backend unavailable", result["summary"])

    def test_evaluate_publish_critic_returns_unavailable_on_bad_json(self):
        module = self._load_module()
        with patch.object(module, "generate_text", return_value="json 없음"):
            result = module.evaluate_publish_critic(_valid_source())

        self.assertEqual(result["status"], "critic_unavailable")
        self.assertTrue(result["raw_excerpt"])


if __name__ == "__main__":
    unittest.main()
