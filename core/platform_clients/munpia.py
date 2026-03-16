from urllib.parse import urlparse
from pathlib import Path

from core.platform_clients.base import (
    BasePlatformClient,
    EpisodeUploadRequest,
    PlatformActionResult,
    PlatformError,
    PlatformWorkMetadata,
)
from core.platform_clients.playwright_session import PlaywrightBrowserSession


class MunpiaClient(BasePlatformClient):
    LOGIN_URL = "https://nssl.munpia.com/login"
    SUPPORTED_PUBLISH_MODES = ("immediate",)
    DEFAULT_SELECTORS = {
        "login_username": "#username",
        "login_password": "#password",
        "login_submit": "button[type='submit']",
        "create_title": "input[name='title']",
        "create_description": "textarea[name='description']",
        "create_submit": "button[type='submit']",
        "episode_title": "input[class*='textfield-module_textfield']",
        "episode_body": "#novelWriteText",
        "episode_submit": "button[class*='button--primary']",
        "episode_confirm_submit": "button[class*='button--primary'][class*='width-block']",
    }

    def __init__(
        self,
        *,
        username: str,
        password: str,
        browser_session=None,
        platform_config: dict | None = None,
        headless: bool = True,
    ):
        self.username = username.strip()
        self.password = password.strip()
        self._browser_session = browser_session
        self.platform_config = platform_config or {}
        self.headless = headless
        self._pending_publish_options: dict | None = None

    def login(self) -> PlatformActionResult:
        self._require_credentials()
        if self._has_saved_session_state():
            return PlatformActionResult(status="done", success=True)
        browser = self._get_browser()
        selectors = self._selectors()
        try:
            browser.goto(self.LOGIN_URL)
            self._ensure_not_security_checkpoint(browser)
            browser.fill(selectors["login_username"], self.username)
            browser.fill(selectors["login_password"], self.password)
            browser.click(selectors["login_submit"])
        except Exception as exc:
            if isinstance(exc, PlatformError):
                raise
            raise self._classify_browser_error(exc) from exc
        return PlatformActionResult(status="done", success=True)

    def ensure_work(self, metadata: PlatformWorkMetadata, work_id: str = "") -> PlatformActionResult:
        if work_id:
            return PlatformActionResult(status="done", success=True, work_id=work_id)

        create_work_url = str(self.platform_config.get("create_work_url", "")).strip()
        if not create_work_url:
            raise PlatformError("Munpia work creation URL is not configured.", error_type="requires_user_action")

        browser = self._get_browser()
        selectors = self._selectors()
        try:
            browser.goto(create_work_url)
            browser.fill(selectors["create_title"], metadata.title)
            browser.fill(selectors["create_description"], metadata.description)
            browser.click(selectors["create_submit"])
        except Exception as exc:
            raise self._classify_browser_error(exc) from exc

        created_work_id = _extract_last_url_segment(browser.current_url)
        return PlatformActionResult(status="done", success=True, work_id=created_work_id)

    def upload_episode(self, request: EpisodeUploadRequest) -> PlatformActionResult:
        if not request.work_id.strip():
            raise PlatformError("Munpia work ID is required for episode upload.", error_type="permanent")

        upload_url_template = str(self.platform_config.get("upload_url_template", "")).strip()
        if not upload_url_template:
            raise PlatformError("Munpia upload URL template is not configured.", error_type="requires_user_action")

        browser = self._get_browser()
        selectors = self._selectors()
        editor_url = upload_url_template.format(work_id=request.work_id)
        try:
            browser.goto(editor_url)
            browser.fill(selectors["episode_title"], request.episode_title)
            browser.fill(selectors["episode_body"], request.content)
            browser.click(selectors["episode_submit"])
            if hasattr(browser, "click_if_present"):
                browser.click_if_present(selectors["episode_confirm_submit"], timeout_ms=3000)
            if hasattr(browser, "wait_for_url_change"):
                if not browser.wait_for_url_change(editor_url, timeout_ms=10000):
                    raise PlatformError(
                        "Munpia episode submission did not reach a completion page.",
                        error_type="retryable",
                    )
            elif browser.current_url == editor_url:
                raise PlatformError(
                    "Munpia episode submission did not leave the editor page.",
                    error_type="retryable",
                )
        except Exception as exc:
            if isinstance(exc, PlatformError):
                raise
            raise self._classify_browser_error(exc) from exc

        return PlatformActionResult(
            status="done",
            success=True,
            work_id=request.work_id,
            episode_id=_extract_episode_id(browser.current_url),
        )

    def set_publish_options(self, payload: dict) -> PlatformActionResult:
        options = _normalize_publish_options(payload)
        if options["publish_mode"] == "reserved":
            raise PlatformError("Munpia reserved scheduling is not configured.", error_type="requires_user_action")
        self._pending_publish_options = options
        return PlatformActionResult(status="done", success=True)

    def verify_publication(self, expected: dict) -> PlatformActionResult:
        work_id = str(expected.get("work_id", "")).strip()
        episode_id = str(expected.get("episode_id", "")).strip()
        upload_url_template = str(self.platform_config.get("upload_url_template", "")).strip()
        if not upload_url_template:
            raise PlatformError("Munpia upload URL template is not configured.", error_type="requires_user_action")

        editor_url = upload_url_template.format(work_id=work_id)
        current_url = str(getattr(self._get_browser(), "current_url", "")).strip()
        if not current_url or current_url == editor_url:
            raise PlatformError(
                "Munpia publication verification is still on the editor page.",
                error_type="retryable",
            )
        if episode_id and episode_id not in current_url:
            raise PlatformError(
                "Munpia publication verification did not reach the expected episode URL.",
                error_type="retryable",
            )

        return PlatformActionResult(
            status="done",
            success=True,
            work_id=work_id,
            episode_id=episode_id or _extract_episode_id(current_url),
        )

    def smoke_check_editor(self, work_id: str) -> PlatformActionResult:
        normalized_work_id = str(work_id).strip()
        if not normalized_work_id:
            raise PlatformError("Munpia work ID is required for smoke check.", error_type="requires_user_action")

        upload_url_template = str(self.platform_config.get("upload_url_template", "")).strip()
        if not upload_url_template:
            raise PlatformError("Munpia upload URL template is not configured.", error_type="requires_user_action")

        browser = self._get_browser()
        selectors = self._selectors()
        editor_url = upload_url_template.format(work_id=normalized_work_id)
        try:
            browser.goto(editor_url)
            required_selectors = (
                selectors["episode_title"],
                selectors["episode_body"],
            )
            for selector in required_selectors:
                if not hasattr(browser, "has_selector") or not browser.has_selector(selector, timeout_ms=3000):
                    raise PlatformError(
                        f"Munpia smoke check could not find required editor selector: {selector}",
                        error_type="retryable",
                    )
        except Exception as exc:
            if isinstance(exc, PlatformError):
                raise
            raise self._classify_browser_error(exc) from exc

        return PlatformActionResult(status="done", success=True, work_id=normalized_work_id)

    def close(self) -> None:
        if self._browser_session is not None:
            self._browser_session.close()
            self._browser_session = None

    def _require_credentials(self) -> None:
        if not self.username or not self.password:
            raise PlatformError("Munpia credentials are missing.", error_type="requires_user_action")

    def _get_browser(self):
        if self._browser_session is None:
            self._browser_session = PlaywrightBrowserSession(
                headless=self.headless,
                storage_state_path=self._resolved_session_state_path(),
            )
        return self._browser_session

    def _selectors(self) -> dict:
        return self.DEFAULT_SELECTORS | self.platform_config.get("selectors", {})

    def _classify_browser_error(self, exc: Exception) -> PlatformError:
        message = str(exc).strip() or exc.__class__.__name__
        lowered = message.lower()
        if "captcha" in lowered or "auth" in lowered or "login" in lowered:
            return PlatformError(message, error_type="requires_user_action")
        if "editor" in lowered or "timeout" in lowered or "missing" in lowered:
            return PlatformError(message, error_type="retryable")
        return PlatformError(message, error_type="permanent")

    def _ensure_not_security_checkpoint(self, browser) -> None:
        content = ""
        if hasattr(browser, "content"):
            try:
                content = str(browser.content() or "")
            except Exception:
                content = ""
        if "문피아 보안 점검 안내" in content:
            raise PlatformError(
                "문피아 보안 점검이 자동 로그인을 차단했습니다. scripts/bootstrap_munpia_session.py로 수동 세션을 저장한 뒤 다시 시도하세요.",
                error_type="requires_user_action",
            )

    def _resolved_session_state_path(self) -> str:
        value = str(self.platform_config.get("session_state_path", "")).strip()
        return value

    def _has_saved_session_state(self) -> bool:
        path = self._resolved_session_state_path()
        return bool(path and Path(path).exists())


def _extract_last_url_segment(url: str) -> str:
    parsed = urlparse(url)
    path_segments = [segment for segment in parsed.path.split("/") if segment]
    if path_segments:
        return path_segments[-1]
    return ""


def _extract_episode_id(url: str) -> str:
    episode_id = _extract_last_url_segment(url)
    if episode_id == "entry-complete":
        return ""
    return episode_id


def _normalize_publish_options(payload: dict | None) -> dict:
    raw = payload if isinstance(payload, dict) else {}
    return {
        "publish_mode": str(raw.get("publish_mode", "immediate") or "immediate").strip().lower(),
        "visibility": str(raw.get("visibility", "public") or "public").strip().lower(),
        "reserved_at": raw.get("reserved_at"),
    }
