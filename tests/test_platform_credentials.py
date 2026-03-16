import unittest
from unittest.mock import patch


class FakeKeyringBackend:
    pass


class FakeFailBackend:
    pass


FakeFailBackend.__module__ = "keyring.backends.fail"


class FakeKeyring:
    def __init__(self):
        self.store = {}
        self.backend = FakeKeyringBackend()

    def get_keyring(self):
        return self.backend

    def get_password(self, service_name, account_name):
        return self.store.get((service_name, account_name))

    def set_password(self, service_name, account_name, value):
        self.store[(service_name, account_name)] = value

    def delete_password(self, service_name, account_name):
        self.store.pop((service_name, account_name), None)


class TestPlatformCredentials(unittest.TestCase):
    def test_save_and_load_munpia_credentials(self):
        module_name = "core.platform_credentials"
        fake_keyring = FakeKeyring()

        with patch(f"{module_name}.keyring", fake_keyring):
            from core.platform_credentials import load_platform_credentials, save_platform_credentials

            ok, _message = save_platform_credentials("sample", "munpia", "writer-id", "secret-pass")
            self.assertTrue(ok)
            payload = load_platform_credentials("sample", "munpia")

        self.assertEqual(payload["username"], "writer-id")
        self.assertEqual(payload["password"], "secret-pass")

    def test_load_missing_credentials_returns_empty_payload(self):
        fake_keyring = FakeKeyring()

        with patch("core.platform_credentials.keyring", fake_keyring):
            from core.platform_credentials import load_platform_credentials

            payload = load_platform_credentials("sample", "novelpia")

        self.assertEqual(payload, {"username": "", "password": ""})

    def test_has_secure_storage_false_for_fail_backend(self):
        fake_keyring = FakeKeyring()
        fake_keyring.backend = FakeFailBackend()

        with patch("core.platform_credentials.keyring", fake_keyring):
            from core.platform_credentials import has_secure_storage

            self.assertFalse(has_secure_storage())

    def test_load_platform_credentials_falls_back_to_env_when_secure_storage_unavailable(self):
        with patch("core.platform_credentials.keyring", None), patch.dict(
            "os.environ",
            {
                "NOVEL_AUTOWRITER_1_MUNPIA_USERNAME": "env-user",
                "NOVEL_AUTOWRITER_1_MUNPIA_PASSWORD": "env-pass",
            },
            clear=True,
        ):
            from core.platform_credentials import load_platform_credentials

            payload = load_platform_credentials("1", "munpia")

        self.assertEqual(payload, {"username": "env-user", "password": "env-pass"})

    def test_load_platform_credentials_prefers_project_scoped_env_over_platform_global_env(self):
        with patch("core.platform_credentials.keyring", None), patch.dict(
            "os.environ",
            {
                "NOVEL_AUTOWRITER_MUNPIA_USERNAME": "global-user",
                "NOVEL_AUTOWRITER_MUNPIA_PASSWORD": "global-pass",
                "NOVEL_AUTOWRITER_SAMPLE_MUNPIA_USERNAME": "project-user",
                "NOVEL_AUTOWRITER_SAMPLE_MUNPIA_PASSWORD": "project-pass",
            },
            clear=True,
        ):
            from core.platform_credentials import load_platform_credentials

            payload = load_platform_credentials("sample", "munpia")

        self.assertEqual(payload, {"username": "project-user", "password": "project-pass"})

    def test_load_platform_credentials_ignores_partial_env_credentials(self):
        with patch("core.platform_credentials.keyring", None), patch.dict(
            "os.environ",
            {
                "NOVEL_AUTOWRITER_NOVELPIA_USERNAME": "only-user",
            },
            clear=True,
        ):
            from core.platform_credentials import load_platform_credentials

            payload = load_platform_credentials("sample", "novelpia")

        self.assertEqual(payload, {"username": "", "password": ""})


if __name__ == "__main__":
    unittest.main()
