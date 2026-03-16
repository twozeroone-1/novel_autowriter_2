import unittest

from core.platform_clients.base import EpisodeUploadRequest, PlatformError, PlatformWorkMetadata


class FakeBrowserSession:
    def __init__(
        self,
        *,
        click_url: str = "",
        click_urls: list[str] | None = None,
        fail_on_fill: str = "",
        present_selectors: set[str] | None = None,
    ):
        self.actions: list[tuple[str, str, str]] = []
        self.current_url = ""
        self.click_urls = list(click_urls or ([click_url] if click_url else []))
        self.fail_on_fill = fail_on_fill
        self.present_selectors = set(present_selectors or set())

    def goto(self, url: str) -> None:
        self.current_url = url
        self.actions.append(("goto", url, ""))

    def fill(self, selector: str, value: str) -> None:
        if self.fail_on_fill:
            raise RuntimeError(self.fail_on_fill)
        self.actions.append(("fill", selector, value))

    def click(self, selector: str) -> None:
        self.actions.append(("click", selector, ""))
        if self.click_urls:
            self.current_url = self.click_urls.pop(0)

    def click_if_present(self, selector: str, timeout_ms: int = 0) -> bool:
        self.actions.append(("click_if_present", selector, str(timeout_ms)))
        if selector not in self.present_selectors:
            return False
        self.click(selector)
        return True

    def wait_for_url_change(self, previous_url: str, timeout_ms: int = 0) -> bool:
        self.actions.append(("wait_for_url_change", previous_url, str(timeout_ms)))
        return self.current_url != previous_url

    def has_selector(self, selector: str, timeout_ms: int = 0) -> bool:
        self.actions.append(("has_selector", selector, str(timeout_ms)))
        return selector in self.present_selectors

    def close(self) -> None:
        self.actions.append(("close", "", ""))


class TestMunpiaClient(unittest.TestCase):
    def test_munpia_client_requires_credentials_before_login(self):
        from core.platform_clients.munpia import MunpiaClient

        client = MunpiaClient(username="", password="", browser_session=FakeBrowserSession())

        with self.assertRaises(PlatformError) as context:
            client.login()

        self.assertEqual(context.exception.error_type, "requires_user_action")

    def test_login_uses_public_login_form_ids(self):
        from core.platform_clients.munpia import MunpiaClient

        browser = FakeBrowserSession()
        client = MunpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
        )

        client.login()

        self.assertEqual(
            browser.actions[:4],
            [
                ("goto", "https://nssl.munpia.com/login", ""),
                ("fill", "#username", "writer-id"),
                ("fill", "#password", "secret"),
                ("click", "button[type='submit']", ""),
            ],
        )

    def test_munpia_client_maps_missing_editor_field_to_retryable_error(self):
        from core.platform_clients.munpia import MunpiaClient

        client = MunpiaClient(
            username="writer-id",
            password="secret",
            browser_session=FakeBrowserSession(fail_on_fill="editor field missing"),
            platform_config={
                "upload_url_template": "https://munpia.test/work/{work_id}/episode/new",
            },
        )

        with self.assertRaises(PlatformError) as context:
            client.upload_episode(
                EpisodeUploadRequest(
                    work_id="work-1",
                    episode_title="Episode 12",
                    content="body",
                )
            )

        self.assertEqual(context.exception.error_type, "retryable")

    def test_ensure_work_returns_existing_work_id_when_present(self):
        from core.platform_clients.munpia import MunpiaClient

        browser = FakeBrowserSession()
        client = MunpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
        )

        result = client.ensure_work(
            PlatformWorkMetadata(title="Project title"),
            work_id="work-1",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.work_id, "work-1")
        self.assertEqual(browser.actions, [])

    def test_upload_episode_returns_episode_id_on_success(self):
        from core.platform_clients.munpia import MunpiaClient

        browser = FakeBrowserSession(click_url="https://munpia.test/work/work-1/episode/episode-7")
        client = MunpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://munpia.test/work/{work_id}/episode/new",
            },
        )

        result = client.upload_episode(
            EpisodeUploadRequest(
                work_id="work-1",
                episode_title="Episode 12",
                content="body",
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.episode_id, "episode-7")

    def test_upload_episode_confirms_modal_before_completion(self):
        from core.platform_clients.munpia import MunpiaClient

        browser = FakeBrowserSession(
            click_urls=[
                "",
                "https://munpia.test/work/work-1/entry-complete",
            ],
            present_selectors={"button[class*='button--primary'][class*='width-block']"},
        )
        client = MunpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://munpia.test/work/{work_id}/episode/new",
            },
        )

        result = client.upload_episode(
            EpisodeUploadRequest(
                work_id="work-1",
                episode_title="Episode 12",
                content="body",
                visibility="private",
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.episode_id, "")
        self.assertEqual(
            browser.actions[3:7],
            [
                ("click", "button[class*='button--primary']", ""),
                ("click_if_present", "button[class*='button--primary'][class*='width-block']", "3000"),
                ("click", "button[class*='button--primary'][class*='width-block']", ""),
                ("wait_for_url_change", "https://munpia.test/work/work-1/episode/new", "10000"),
            ],
        )

    def test_upload_episode_raises_retryable_when_editor_page_does_not_complete(self):
        from core.platform_clients.munpia import MunpiaClient

        browser = FakeBrowserSession()
        client = MunpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://munpia.test/work/{work_id}/episode/new",
            },
        )

        with self.assertRaises(PlatformError) as context:
            client.upload_episode(
                EpisodeUploadRequest(
                    work_id="work-1",
                    episode_title="Episode 12",
                    content="body",
                    visibility="private",
                )
            )

        self.assertEqual(context.exception.error_type, "retryable")

    def test_upload_episode_uses_writer_form_selectors(self):
        from core.platform_clients.munpia import MunpiaClient

        browser = FakeBrowserSession(click_url="https://munpia.test/work/work-1/episode/episode-7")
        client = MunpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://munpia.test/work/{work_id}/episode/new",
            },
        )

        client.upload_episode(
            EpisodeUploadRequest(
                work_id="work-1",
                episode_title="Episode 12",
                content="body",
            )
        )

        self.assertEqual(
            browser.actions[:4],
            [
                ("goto", "https://munpia.test/work/work-1/episode/new", ""),
                ("fill", "input[class*='textfield-module_textfield']", "Episode 12"),
                ("fill", "#novelWriteText", "body"),
                ("click", "button[class*='button--primary']", ""),
            ],
        )

    def test_set_publish_options_accepts_immediate_private_mode(self):
        from core.platform_clients.munpia import MunpiaClient

        client = MunpiaClient(
            username="writer-id",
            password="secret",
            browser_session=FakeBrowserSession(),
            platform_config={"upload_url_template": "https://munpia.test/work/{work_id}/episode/new"},
        )

        result = client.set_publish_options(
            {
                "publish_mode": "immediate",
                "visibility": "private",
                "reserved_at": None,
            }
        )

        self.assertTrue(result.success)

    def test_set_publish_options_rejects_reserved_mode(self):
        from core.platform_clients.munpia import MunpiaClient

        client = MunpiaClient(
            username="writer-id",
            password="secret",
            browser_session=FakeBrowserSession(),
            platform_config={"upload_url_template": "https://munpia.test/work/{work_id}/episode/new"},
        )

        with self.assertRaises(PlatformError) as context:
            client.set_publish_options(
                {
                    "publish_mode": "reserved",
                    "visibility": "private",
                    "reserved_at": "2026-03-16T21:00:00+09:00",
                }
            )

        self.assertEqual(context.exception.error_type, "requires_user_action")

    def test_supported_publish_modes_only_include_immediate(self):
        from core.platform_clients.munpia import MunpiaClient

        self.assertEqual(MunpiaClient.supported_publish_modes(), ("immediate",))

    def test_smoke_check_editor_succeeds_when_required_fields_exist(self):
        from core.platform_clients.munpia import MunpiaClient

        browser = FakeBrowserSession(
            present_selectors={
                "input[class*='textfield-module_textfield']",
                "#novelWriteText",
            }
        )
        client = MunpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://munpia.test/work/{work_id}/episode/new",
            },
        )

        result = client.smoke_check_editor("work-1")

        self.assertTrue(result.success)
        self.assertEqual(result.work_id, "work-1")
        self.assertEqual(
            browser.actions[:3],
            [
                ("goto", "https://munpia.test/work/work-1/episode/new", ""),
                ("has_selector", "input[class*='textfield-module_textfield']", "3000"),
                ("has_selector", "#novelWriteText", "3000"),
            ],
        )

    def test_verify_publication_succeeds_for_completed_episode_url(self):
        from core.platform_clients.munpia import MunpiaClient

        browser = FakeBrowserSession()
        browser.current_url = "https://munpia.test/work/work-1/episode/episode-7"
        client = MunpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://munpia.test/work/{work_id}/episode/new",
            },
        )

        result = client.verify_publication({"work_id": "work-1", "episode_id": "episode-7"})

        self.assertTrue(result.success)
        self.assertEqual(result.episode_id, "episode-7")

    def test_verify_publication_fails_retryably_when_still_on_editor_url(self):
        from core.platform_clients.munpia import MunpiaClient

        browser = FakeBrowserSession()
        browser.current_url = "https://munpia.test/work/work-1/episode/new"
        client = MunpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://munpia.test/work/{work_id}/episode/new",
            },
        )

        with self.assertRaises(PlatformError) as context:
            client.verify_publication({"work_id": "work-1", "episode_id": "episode-7"})

        self.assertEqual(context.exception.error_type, "retryable")


if __name__ == "__main__":
    unittest.main()
