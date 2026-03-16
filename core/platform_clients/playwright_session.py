import time

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    sync_playwright = None

class PlaywrightBrowserSession:
    def __init__(self, *, headless: bool = True):
        if sync_playwright is None:
            raise RuntimeError(
                "Playwright is not installed. Run `python -m pip install playwright` "
                "and `python -m playwright install chromium` first."
            )
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=headless)
        self._page = self._browser.new_page()

    @property
    def current_url(self) -> str:
        return self._page.url

    def goto(self, url: str) -> None:
        self._page.goto(url, wait_until="domcontentloaded")

    def fill(self, selector: str, value: str) -> None:
        self._page.locator(selector).first.fill(value)

    def click(self, selector: str) -> None:
        self._page.locator(selector).first.click()

    def select_option(self, selector: str, value: str) -> None:
        self._page.locator(selector).first.select_option(value)

    def set_multi_select_values(self, selector: str, values: list[str]) -> None:
        locator = self._page.locator(selector).first
        locator.evaluate(
            """(element, values) => {
                for (const value of values) {
                    let option = Array.from(element.options).find(
                        (candidate) => candidate.value === value || candidate.text === value
                    );
                    if (!option || option.value !== value) {
                        option = new Option(value, value, true, true);
                        element.add(option);
                    }
                    option.selected = true;
                    option.setAttribute("selected", "selected");
                }
                element.dispatchEvent(new Event("input", { bubbles: true }));
                element.dispatchEvent(new Event("change", { bubbles: true }));
                if (window.jQuery) {
                    window.jQuery(element).trigger("change");
                }
            }""",
            values,
        )

    def click_if_present(self, selector: str, timeout_ms: int = 0) -> bool:
        locator = self._page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=timeout_ms)
        except Exception:
            return False
        locator.click()
        return True

    def wait_for_url_change(self, previous_url: str, timeout_ms: int = 0) -> bool:
        deadline = time.time() + (timeout_ms / 1000.0)
        while time.time() < deadline:
            if self._page.url != previous_url:
                return True
            self._page.wait_for_timeout(200)
        return self._page.url != previous_url

    def content(self) -> str:
        return self._page.content()

    def has_selector(self, selector: str, timeout_ms: int = 0) -> bool:
        locator = self._page.locator(selector).first
        try:
            locator.wait_for(state="attached", timeout=timeout_ms)
        except Exception:
            return False
        return True

    def close(self) -> None:
        self._browser.close()
        self._playwright.stop()
