import tempfile
import unittest
from pathlib import Path


class FakeBootstrapBrowser:
    def __init__(self):
        self.visited_urls = []
        self.saved_paths = []
        self.closed = False

    def goto(self, url: str) -> None:
        self.visited_urls.append(url)

    def save_storage_state(self, path: Path) -> None:
        self.saved_paths.append(str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    def close(self) -> None:
        self.closed = True


class TestMunpiaSessionBootstrap(unittest.TestCase):
    def test_bootstrap_saves_manual_login_session_state(self):
        from core.munpia_session_bootstrap import bootstrap_munpia_session

        browser = FakeBootstrapBrowser()
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "publishing" / "sessions" / "munpia.json"
            saved_path = bootstrap_munpia_session(
                login_url="https://nssl.munpia.com/login",
                state_path=state_path,
                browser_session_factory=lambda: browser,
                wait_for_confirmation=lambda: None,
            )

        self.assertEqual(browser.visited_urls, ["https://nssl.munpia.com/login"])
        self.assertEqual(browser.saved_paths, [str(state_path)])
        self.assertTrue(browser.closed)
        self.assertEqual(saved_path, state_path)
