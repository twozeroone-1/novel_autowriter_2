import unittest


class TestPlatformSessionStore(unittest.TestCase):
    def test_session_state_path_uses_project_publishing_sessions_directory(self):
        from core.platform_session_store import PlatformSessionStore

        store = PlatformSessionStore("sample")

        path = store.session_state_path("munpia")

        self.assertEqual(path.name, "munpia.json")
        self.assertEqual(path.parent.name, "sessions")
        self.assertEqual(path.parent.parent.name, "publishing")
        self.assertIn("sample", str(path))
