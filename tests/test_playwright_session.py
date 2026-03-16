import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class FakePage:
    def __init__(self):
        self.url = ""


class FakeContext:
    def __init__(self):
        self.page = FakePage()
        self.saved_paths = []

    def new_page(self):
        return self.page

    def storage_state(self, *, path: str):
        self.saved_paths.append(path)

    def close(self):
        return None


class FakeBrowser:
    def __init__(self):
        self.new_context_calls = []
        self.context = FakeContext()

    def new_context(self, **kwargs):
        self.new_context_calls.append(kwargs)
        return self.context

    def close(self):
        return None


class FakeChromium:
    def __init__(self):
        self.browser = FakeBrowser()
        self.launch_calls = []

    def launch(self, *, headless: bool):
        self.launch_calls.append(headless)
        return self.browser


class FakePlaywrightManager:
    def __init__(self):
        self.chromium = FakeChromium()
        self.stopped = False

    def start(self):
        return self

    def stop(self):
        self.stopped = True


class TestPlaywrightBrowserSession(unittest.TestCase):
    def test_session_uses_storage_state_path_when_present(self):
        fake_manager = FakePlaywrightManager()

        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "munpia.json"
            state_path.write_text("{}", encoding="utf-8")
            with patch("core.platform_clients.playwright_session.sync_playwright", lambda: fake_manager):
                from core.platform_clients.playwright_session import PlaywrightBrowserSession

                session = PlaywrightBrowserSession(headless=True, storage_state_path=state_path)
                session.close()

        self.assertEqual(
            fake_manager.chromium.browser.new_context_calls,
            [{"storage_state": str(state_path)}],
        )

    def test_save_storage_state_persists_context_to_target_path(self):
        fake_manager = FakePlaywrightManager()

        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "nested" / "munpia.json"
            with patch("core.platform_clients.playwright_session.sync_playwright", lambda: fake_manager):
                from core.platform_clients.playwright_session import PlaywrightBrowserSession

                session = PlaywrightBrowserSession(headless=True)
                session.save_storage_state(state_path)
                self.assertTrue(state_path.parent.exists())
                session.close()

        self.assertEqual(fake_manager.chromium.browser.context.saved_paths, [str(state_path)])
