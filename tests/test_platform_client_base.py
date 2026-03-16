import importlib
import importlib.util
import unittest


class TestPlatformClientBase(unittest.TestCase):
    def test_platform_action_result_carries_status_and_identifiers(self):
        spec = importlib.util.find_spec("core.platform_clients.base")
        self.assertIsNotNone(spec, "core.platform_clients.base should exist")
        module = importlib.import_module("core.platform_clients.base")

        result = module.PlatformActionResult(
            status="done",
            success=True,
            work_id="work-1",
            episode_id="episode-1",
        )

        self.assertEqual(result.status, "done")
        self.assertTrue(result.success)
        self.assertEqual(result.work_id, "work-1")
        self.assertEqual(result.episode_id, "episode-1")

    def test_platform_error_carries_classification(self):
        module = importlib.import_module("core.platform_clients.base")

        error = module.PlatformError("captcha required", error_type="requires_user_action")

        self.assertEqual(str(error), "captcha required")
        self.assertEqual(error.error_type, "requires_user_action")

    def test_base_platform_client_exposes_verify_publication_contract(self):
        module = importlib.import_module("core.platform_clients.base")

        method = getattr(module.BasePlatformClient, "verify_publication", None)

        self.assertIsNotNone(method)
        self.assertTrue(getattr(method, "__isabstractmethod__", False))

    def test_base_platform_client_exposes_set_publish_options_contract(self):
        module = importlib.import_module("core.platform_clients.base")

        method = getattr(module.BasePlatformClient, "set_publish_options", None)

        self.assertIsNotNone(method)
        self.assertTrue(getattr(method, "__isabstractmethod__", False))


if __name__ == "__main__":
    unittest.main()
