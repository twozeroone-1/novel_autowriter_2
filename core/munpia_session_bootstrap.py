from pathlib import Path

from core.platform_clients.munpia import MunpiaClient
from core.platform_clients.playwright_session import PlaywrightBrowserSession


def bootstrap_munpia_session(
    *,
    login_url: str = MunpiaClient.LOGIN_URL,
    state_path: Path,
    browser_session_factory=None,
    wait_for_confirmation=None,
) -> Path:
    build_browser = browser_session_factory or (lambda: PlaywrightBrowserSession(headless=False))
    confirm = wait_for_confirmation or (lambda: input("문피아 로그인 완료 후 Enter를 누르세요. "))
    browser = build_browser()
    try:
        browser.goto(login_url)
        confirm()
        browser.save_storage_state(state_path)
        return state_path
    finally:
        browser.close()
