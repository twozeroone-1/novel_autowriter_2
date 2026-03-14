import importlib
import importlib.util
import unittest
from unittest.mock import patch


class TestCanonExtractor(unittest.TestCase):
    def _load_module(self):
        spec = importlib.util.find_spec("core.canon_extractor")
        self.assertIsNotNone(spec, "core.canon_extractor should exist")
        return importlib.import_module("core.canon_extractor")

    def test_extract_canon_update_parses_json_object_from_llm_response(self):
        module = self._load_module()
        with patch.object(
            module,
            "generate_text",
            return_value='분석 결과입니다.\n{"people":{"lead":{"mood":"angry"}},"resources":{"cash":1200},"hooks":["new hook"],"timeline":["ep_012"]}',
        ):
            payload = module.extract_canon_update("chapter text", project_name="sample")

        self.assertEqual(payload["people"]["lead"]["mood"], "angry")
        self.assertEqual(payload["resources"]["cash"], 1200)
        self.assertEqual(payload["hooks"], ["new hook"])
        self.assertEqual(payload["timeline"], ["ep_012"])

    def test_extract_canon_update_normalizes_partial_payload(self):
        module = self._load_module()
        with patch.object(
            module,
            "generate_text",
            return_value='{"people":{"lead":{"status":"wounded"}},"hooks":["pending duel"]}',
        ):
            payload = module.extract_canon_update("chapter text", project_name="sample")

        self.assertEqual(payload["people"]["lead"]["status"], "wounded")
        self.assertEqual(payload["resources"], {})
        self.assertEqual(payload["hooks"], ["pending duel"])
        self.assertEqual(payload["timeline"], [])

    def test_extract_canon_update_rejects_missing_json_payload(self):
        module = self._load_module()
        with patch.object(module, "generate_text", return_value="json이 없습니다"):
            with self.assertRaises(ValueError):
                module.extract_canon_update("chapter text", project_name="sample")


if __name__ == "__main__":
    unittest.main()
