from datetime import datetime
from urllib.parse import urlparse
import re

from core.platform_clients.base import (
    BasePlatformClient,
    EpisodeUploadRequest,
    PlatformActionResult,
    PlatformError,
    PlatformWorkMetadata,
)
from core.platform_clients.playwright_session import PlaywrightBrowserSession


class NovelpiaClient(BasePlatformClient):
    LOGIN_URL = "https://novelpia.com/mybook/mynovel"
    WRITER_ROOM_URL = "https://novelpia.com/writer_room"
    DEFAULT_SELECTORS = {
        "login_username": "input[name='email']",
        "login_password": "input[name='wd']",
        "login_submit": "button[type='submit']",
        "create_title": "input[name='novel_name']",
        "create_description": "textarea[name='novel_story']",
        "create_novel_type": "select[name='novel_type']",
        "create_monopoly": "select[name='is_monopoly']",
        "create_age_grade": "select[name='novel_age']",
        "create_main_genre": "#main_genre",
        "create_hashtags": "select[name='novel_genre[]']",
        "create_submit": "#btn_save_novel",
        "create_challenge_cancel": ".btn_challenge_cancel:visible",
        "dismiss_event_overlay": ".event-plus-close:visible",
        "dismiss_event_overlay_secondary": "p.later-close:visible",
        "episode_category": "#content_cate",
        "episode_title": "#content_subject",
        "episode_body": ".note-editable",
        "episode_submit": ".btn.btn-block.btn-primary.s_inv",
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
        browser = self._get_browser()
        selectors = self._selectors()
        try:
            browser.goto(self._login_url())
            browser.fill(selectors["login_username"], self.username)
            browser.fill(selectors["login_password"], self.password)
            browser.click(selectors["login_submit"])
        except Exception as exc:
            raise self._classify_browser_error(exc) from exc
        return PlatformActionResult(status="done", success=True)

    def ensure_work(self, metadata: PlatformWorkMetadata, work_id: str = "") -> PlatformActionResult:
        if work_id:
            return PlatformActionResult(status="done", success=True, work_id=work_id)

        create_work_url = str(self.platform_config.get("create_work_url", "")).strip()
        if not create_work_url:
            raise PlatformError("Novelpia work creation URL is not configured.", error_type="requires_user_action")

        title = metadata.title.strip()
        if not title:
            raise PlatformError("Novelpia work title is required.", error_type="requires_user_action")

        genre_value = _main_genre_value(metadata.genre)
        if not genre_value:
            raise PlatformError("Novelpia main genre is required.", error_type="requires_user_action")
        hashtag_values = _hashtag_values(
            genre_value,
            self.platform_config.get("hashtags", []),
        )
        if len(hashtag_values) < 2:
            raise PlatformError("Novelpia requires at least two hashtags.", error_type="requires_user_action")

        browser = self._get_browser()
        selectors = self._selectors()
        try:
            browser.goto(create_work_url)
            browser.fill(selectors["create_title"], title)
            browser.fill(selectors["create_description"], metadata.description)
            browser.select_option(selectors["create_novel_type"], "2")
            browser.select_option(selectors["create_monopoly"], "0")
            browser.select_option(selectors["create_age_grade"], _age_grade_value(metadata.age_grade))
            browser.select_option(selectors["create_main_genre"], genre_value)
            if hasattr(browser, "set_multi_select_values"):
                browser.set_multi_select_values(selectors["create_hashtags"], hashtag_values)
            else:
                browser.select_option(selectors["create_hashtags"], hashtag_values)
            if hasattr(browser, "click_if_present"):
                dismissed = browser.click_if_present(selectors["dismiss_event_overlay"], timeout_ms=2000)
                if not dismissed:
                    browser.click_if_present(selectors["dismiss_event_overlay_secondary"], timeout_ms=1000)
                browser.click_if_present(selectors["create_challenge_cancel"], timeout_ms=2000)
            browser.click(selectors["create_submit"])
            if hasattr(browser, "wait_for_url_change"):
                if not browser.wait_for_url_change(create_work_url, timeout_ms=10000):
                    raise PlatformError(
                        "Novelpia work creation did not leave the create page.",
                        error_type="retryable",
                    )
            elif browser.current_url == create_work_url:
                raise PlatformError(
                    "Novelpia work creation did not leave the create page.",
                    error_type="retryable",
                )
        except Exception as exc:
            if isinstance(exc, PlatformError):
                raise
            raise self._classify_browser_error(exc) from exc

        browser.goto(self.WRITER_ROOM_URL)
        created_work_id = _extract_novelpia_writer_room_work_id(browser.content(), title)
        if not created_work_id:
            raise PlatformError("Novelpia work creation did not yield a work ID.", error_type="retryable")
        return PlatformActionResult(status="done", success=True, work_id=created_work_id)

    def upload_episode(self, request: EpisodeUploadRequest) -> PlatformActionResult:
        if not request.work_id.strip():
            raise PlatformError("Novelpia work ID is required for episode upload.", error_type="permanent")

        upload_url_template = str(self.platform_config.get("upload_url_template", "")).strip()
        browser = self._get_browser()
        selectors = self._selectors()
        editor_url = _episode_editor_url(upload_url_template, request.work_id)
        try:
            browser.goto(editor_url)
            browser.fill(selectors["episode_title"], request.episode_title)
            browser.fill(selectors["episode_body"], request.content)
            pending_options = self._pending_publish_options if isinstance(self._pending_publish_options, dict) else {}
            effective_publish_mode = (
                str(pending_options.get("publish_mode", "")).strip().lower() or request.publish_mode
            )
            if hasattr(browser, "select_option"):
                effective_visibility = (
                    str(pending_options.get("visibility", "")).strip() or request.visibility
                )
                browser.select_option(
                    selectors["episode_category"],
                    _content_category_value(effective_visibility),
                )
            if effective_publish_mode == "reserved":
                reserved_date, reserved_time = _reserved_date_and_time(pending_options)
                browser.click(_required_selector(selectors, "episode_publish_mode_reserved"))
                browser.fill(_required_selector(selectors, "episode_reserved_date"), reserved_date)
                browser.fill(_required_selector(selectors, "episode_reserved_time"), reserved_time)
            if hasattr(browser, "click_if_present"):
                dismissed = browser.click_if_present(selectors["dismiss_event_overlay"], timeout_ms=2000)
                if not dismissed:
                    browser.click_if_present(selectors["dismiss_event_overlay_secondary"], timeout_ms=1000)
            browser.click(selectors["episode_submit"])
            if hasattr(browser, "wait_for_url_change"):
                if not browser.wait_for_url_change(editor_url, timeout_ms=10000):
                    raise PlatformError(
                        "Novelpia episode submission did not leave the editor page.",
                        error_type="retryable",
                    )
                if effective_publish_mode != "reserved" and browser.current_url.endswith("write_proc") and not browser.wait_for_url_change(
                    browser.current_url,
                    timeout_ms=10000,
                ):
                    raise PlatformError(
                        "Novelpia episode submission did not reach the viewer page.",
                        error_type="retryable",
                    )
            elif browser.current_url == editor_url:
                raise PlatformError(
                    "Novelpia episode submission did not leave the editor page.",
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
            episode_id=_extract_numeric_url_segment(browser.current_url),
        )

    def set_publish_options(self, payload: dict) -> PlatformActionResult:
        options = _normalize_publish_options(payload)
        if options["publish_mode"] == "reserved":
            options["reserved_at"] = _normalize_reserved_at(options.get("reserved_at"))
        self._pending_publish_options = options
        return PlatformActionResult(status="done", success=True)

    def verify_publication(self, expected: dict) -> PlatformActionResult:
        work_id = str(expected.get("work_id", "")).strip()
        episode_id = str(expected.get("episode_id", "")).strip()
        publish_mode = str(expected.get("publish_mode", "immediate") or "immediate").strip().lower()
        verification_mode = str(expected.get("verification_mode", "") or "").strip().lower()
        current_url = str(getattr(self._get_browser(), "current_url", "")).strip()
        editor_url = _episode_editor_url(str(self.platform_config.get("upload_url_template", "")).strip(), work_id)
        if verification_mode == "scheduled_follow_up":
            return self._verify_scheduled_follow_up(expected=expected)

        if not current_url or current_url == editor_url or "write_proc" in current_url:
            raise PlatformError(
                "Novelpia publication verification did not reach the viewer page.",
                error_type="retryable",
            )
        if publish_mode == "reserved" and _looks_like_reserved_confirmation(current_url=current_url, work_id=work_id):
            return PlatformActionResult(
                status="scheduled",
                success=True,
                work_id=work_id,
                episode_id=episode_id,
            )
        if episode_id and episode_id not in current_url:
            raise PlatformError(
                "Novelpia publication verification did not reach the expected episode URL.",
                error_type="retryable",
            )

        return PlatformActionResult(
            status="done",
            success=True,
            work_id=work_id,
            episode_id=episode_id or _extract_numeric_url_segment(current_url),
        )

    def close(self) -> None:
        if self._browser_session is not None:
            self._browser_session.close()
            self._browser_session = None

    def _verify_scheduled_follow_up(self, *, expected: dict) -> PlatformActionResult:
        work_id = str(expected.get("work_id", "")).strip()
        episode_id = str(expected.get("episode_id", "")).strip()
        episode_title = str(expected.get("episode_title", "")).strip()
        if not work_id:
            raise PlatformError("Novelpia scheduled verification requires a work ID.", error_type="requires_user_action")
        if not episode_title:
            raise PlatformError(
                "Novelpia scheduled verification requires an episode title.",
                error_type="requires_user_action",
            )

        browser = self._get_browser()
        listing_url = _novelpia_work_listing_url(work_id=work_id)
        browser.goto(listing_url)
        if episode_title not in browser.content():
            raise PlatformError(
                "Novelpia scheduled publication is not visible on the work listing yet.",
                error_type="retryable",
            )
        return PlatformActionResult(
            status="done",
            success=True,
            work_id=work_id,
            episode_id=episode_id,
        )

    def _require_credentials(self) -> None:
        if not self.username or not self.password:
            raise PlatformError("Novelpia credentials are missing.", error_type="requires_user_action")

    def _get_browser(self):
        if self._browser_session is None:
            self._browser_session = PlaywrightBrowserSession(headless=self.headless)
        return self._browser_session

    def _selectors(self) -> dict:
        return self.DEFAULT_SELECTORS | self.platform_config.get("selectors", {})

    def _login_url(self) -> str:
        create_work_url = str(self.platform_config.get("create_work_url", "")).strip()
        if create_work_url:
            return create_work_url
        return self.LOGIN_URL

    def _classify_browser_error(self, exc: Exception) -> PlatformError:
        message = str(exc).strip() or exc.__class__.__name__
        lowered = message.lower()
        if "captcha" in lowered or "auth" in lowered or "login" in lowered:
            return PlatformError(message, error_type="requires_user_action")
        if "editor" in lowered or "timeout" in lowered or "missing" in lowered:
            return PlatformError(message, error_type="retryable")
        return PlatformError(message, error_type="permanent")


def _extract_numeric_url_segment(url: str) -> str:
    parsed = urlparse(url)
    path_segments = [segment for segment in parsed.path.split("/") if segment]
    for segment in reversed(path_segments):
        if segment.isdigit():
            return segment
    return ""


def _content_category_value(visibility: str) -> str:
    if str(visibility).strip().lower() == "private":
        return "5"
    return "24"


def _normalize_publish_options(payload: dict | None) -> dict:
    raw = payload if isinstance(payload, dict) else {}
    return {
        "publish_mode": str(raw.get("publish_mode", "immediate") or "immediate").strip().lower(),
        "visibility": str(raw.get("visibility", "public") or "public").strip().lower(),
        "reserved_at": raw.get("reserved_at"),
    }


def _age_grade_value(age_grade: str) -> str:
    normalized = str(age_grade).strip().lower()
    if normalized in {"adult", "19", "19+"}:
        return "19"
    if normalized in {"15", "15+"}:
        return "15"
    return "0"


def _main_genre_value(raw_genre: str) -> str:
    genre = str(raw_genre).strip()
    if not genre:
        return ""
    normalized = genre.lower()
    aliases = {
        "1": "1",
        "판타지": "1",
        "fantasy": "1",
        "2": "2",
        "무협": "2",
        "martial": "2",
        "3": "3",
        "현대": "3",
        "modern": "3",
        "6": "6",
        "로맨스": "6",
        "romance": "6",
        "12": "12",
        "현대판타지": "12",
        "urban fantasy": "12",
        "13": "13",
        "라이트노벨": "13",
        "lightnovel": "13",
        "light novel": "13",
        "5": "5",
        "고수위": "5",
        "adult": "5",
        "14": "14",
        "공포": "14",
        "horror": "14",
        "9": "9",
        "sf": "9",
        "sci-fi": "9",
        "8": "8",
        "스포츠": "8",
        "sports": "8",
        "7": "7",
        "대체역사": "7",
        "alt-history": "7",
        "alternate history": "7",
        "10": "10",
        "기타": "10",
        "other": "10",
        "11": "11",
        "패러디": "11",
        "parody": "11",
    }
    return aliases.get(normalized, genre if genre.isdigit() else "")


def _hashtag_values(main_genre: str, configured_hashtags) -> list[str]:
    allowed_tags = {
        "판타지",
        "라이트노벨",
        "전생",
        "현대",
        "중세",
        "하렘",
        "드라마",
        "일상",
        "로맨스",
        "SF",
        "스포츠",
        "무협",
    }
    configured = []
    if isinstance(configured_hashtags, list):
        configured = [str(value).strip() for value in configured_hashtags]
    elif isinstance(configured_hashtags, str):
        configured = [item.strip() for item in configured_hashtags.split(",")]

    selected = []
    for value in configured:
        if value in allowed_tags and value not in selected:
            selected.append(value)

    if len(selected) >= 2:
        return selected[:2]

    defaults_by_genre = {
        "1": ["판타지", "중세"],
        "2": ["무협", "드라마"],
        "3": ["현대", "드라마"],
        "5": ["판타지", "하렘"],
        "6": ["로맨스", "일상"],
        "7": ["중세", "드라마"],
        "8": ["스포츠", "현대"],
        "9": ["SF", "현대"],
        "10": ["드라마", "일상"],
        "11": ["판타지", "라이트노벨"],
        "12": ["현대", "판타지"],
        "13": ["라이트노벨", "일상"],
        "14": ["현대", "드라마"],
    }
    for value in defaults_by_genre.get(main_genre, []):
        if value in allowed_tags and value not in selected:
            selected.append(value)
        if len(selected) >= 2:
            break
    return selected


def _normalize_reserved_at(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlatformError("Novelpia reserved publish requires a reservation time.", error_type="requires_user_action")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise PlatformError("Novelpia reserved publish time is invalid.", error_type="requires_user_action") from exc
    return parsed.isoformat()


def _reserved_date_and_time(options: dict) -> tuple[str, str]:
    reserved_at = _normalize_reserved_at(options.get("reserved_at"))
    parsed = datetime.fromisoformat(reserved_at)
    return parsed.date().isoformat(), parsed.strftime("%H:%M")


def _required_selector(selectors: dict, key: str) -> str:
    selector = str(selectors.get(key, "")).strip()
    if selector:
        return selector
    raise PlatformError(f"Novelpia reserved selector '{key}' is not configured.", error_type="requires_user_action")


def _looks_like_reserved_confirmation(*, current_url: str, work_id: str) -> bool:
    lowered = current_url.lower()
    if any(token in lowered for token in ("scheduled", "schedule", "reserved", "reserve")):
        return True
    if work_id and f"/mynovel/all/{work_id}" in lowered and "/mynovel/all/write/" not in lowered:
        return True
    return False


def _episode_editor_url(upload_url_template: str, work_id: str) -> str:
    template = str(upload_url_template).strip()
    normalized_work_id = str(work_id).strip()
    if not normalized_work_id:
        return template
    if "{work_id}" in template:
        return template.format(work_id=normalized_work_id)
    if "novelpia.com/mynovel/all/write/" in template:
        return f"https://novelpia.com/mynovel/all/write/{normalized_work_id}"
    if template:
        return template
    return f"https://novelpia.com/mynovel/all/write/{normalized_work_id}"


def _novelpia_work_listing_url(*, work_id: str) -> str:
    return f"https://novelpia.com/mynovel/all/{str(work_id).strip()}"


def _extract_novelpia_writer_room_work_id(html: str, title: str) -> str:
    if not html or not title:
        return ""
    title_index = html.find(title)
    if title_index == -1:
        return ""
    forward_window = html[title_index : min(len(html), title_index + 4000)]
    match = re.search(r"/mynovel/all/write/(\d+)", forward_window)
    if match:
        return match.group(1)
    match = re.search(r"/novel/(\d+)", forward_window)
    if match:
        return match.group(1)
    backward_window = html[max(0, title_index - 2000) : title_index]
    match = re.search(r"/mynovel/all/write/(\d+)", backward_window)
    if match:
        return match.group(1)
    match = re.search(r"/novel/(\d+)", backward_window)
    if match:
        return match.group(1)
    return ""
