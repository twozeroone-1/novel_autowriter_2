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
        page_contents: dict[str, str] | None = None,
    ):
        self.actions: list[tuple[str, str, str]] = []
        self.current_url = ""
        self.click_urls = list(click_urls or ([click_url] if click_url else []))
        self.fail_on_fill = fail_on_fill
        self.present_selectors = set(present_selectors or set())
        self.page_contents = dict(page_contents or {})

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

    def select_option(self, selector: str, value: str) -> None:
        self.actions.append(("select_option", selector, value))

    def set_multi_select_values(self, selector: str, values) -> None:
        self.actions.append(("set_multi_select_values", selector, list(values)))

    def click_if_present(self, selector: str, timeout_ms: int = 0) -> bool:
        self.actions.append(("click_if_present", selector, str(timeout_ms)))
        if selector not in self.present_selectors:
            return False
        self.click(selector)
        return True

    def wait_for_url_change(self, previous_url: str, timeout_ms: int = 0) -> bool:
        self.actions.append(("wait_for_url_change", previous_url, str(timeout_ms)))
        if self.current_url == previous_url and self.click_urls:
            self.current_url = self.click_urls.pop(0)
        return self.current_url != previous_url

    def content(self) -> str:
        self.actions.append(("content", self.current_url, ""))
        return self.page_contents.get(self.current_url, "")

    def has_selector(self, selector: str, timeout_ms: int = 0) -> bool:
        self.actions.append(("has_selector", selector, str(timeout_ms)))
        return selector in self.present_selectors

    def close(self) -> None:
        self.actions.append(("close", "", ""))


class TestNovelpiaClient(unittest.TestCase):
    def test_novelpia_client_requires_credentials_before_login(self):
        from core.platform_clients.novelpia import NovelpiaClient

        client = NovelpiaClient(username="", password="", browser_session=FakeBrowserSession())

        with self.assertRaises(PlatformError) as context:
            client.login()

        self.assertEqual(context.exception.error_type, "requires_user_action")

    def test_login_uses_main_site_email_form_on_writer_entry(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession()
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "create_work_url": "https://novelpia.com/publishing/new",
            },
        )

        client.login()

        self.assertEqual(
            browser.actions[:4],
            [
                ("goto", "https://novelpia.com/publishing/new", ""),
                ("fill", "input[name='email']", "writer-id"),
                ("fill", "input[name='wd']", "secret"),
                ("click", "button[type='submit']", ""),
            ],
        )

    def test_novelpia_client_classifies_additional_auth_as_user_action(self):
        from core.platform_clients.novelpia import NovelpiaClient

        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=FakeBrowserSession(fail_on_fill="additional auth required"),
            platform_config={
                "upload_url_template": "https://cp.novelpia.com/work/{work_id}/episode/new",
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

        self.assertEqual(context.exception.error_type, "requires_user_action")

    def test_ensure_work_returns_existing_work_id_when_present(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession()
        client = NovelpiaClient(
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

    def test_ensure_work_uses_real_create_form_fields_and_defaults(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession(
            click_url="https://novelpia.com/publishing/new_proc",
            page_contents={
                "https://novelpia.com/writer_room": """
                <div class="novel_416999">
                    <b class="name_st">Project title</b>
                    <a href="/mynovel/all/write/416999">episode</a>
                </div>
                """
            },
        )
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "create_work_url": "https://novelpia.com/publishing/new",
            },
        )

        result = client.ensure_work(
            PlatformWorkMetadata(
                title="Project title",
                description="desc",
                genre="현대판타지",
                age_grade="adult",
            ),
            work_id="",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.work_id, "416999")
        self.assertEqual(
            browser.actions[:15],
            [
                ("goto", "https://novelpia.com/publishing/new", ""),
                ("fill", "input[name='novel_name']", "Project title"),
                ("fill", "textarea[name='novel_story']", "desc"),
                ("select_option", "select[name='novel_type']", "2"),
                ("select_option", "select[name='is_monopoly']", "0"),
                ("select_option", "select[name='novel_age']", "19"),
                ("select_option", "#main_genre", "12"),
                ("set_multi_select_values", "select[name='novel_genre[]']", ["현대", "판타지"]),
                ("click_if_present", ".event-plus-close:visible", "2000"),
                ("click_if_present", "p.later-close:visible", "1000"),
                ("click_if_present", ".btn_challenge_cancel:visible", "2000"),
                ("click", "#btn_save_novel", ""),
                ("wait_for_url_change", "https://novelpia.com/publishing/new", "10000"),
                ("goto", "https://novelpia.com/writer_room", ""),
                ("content", "https://novelpia.com/writer_room", ""),
            ],
        )

    def test_ensure_work_dismisses_new_challenge_modal_when_present(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession(
            click_url="https://novelpia.com/publishing/new_proc",
            present_selectors={".btn_challenge_cancel:visible"},
            page_contents={
                "https://novelpia.com/writer_room": """
                <div class="novel_416999">
                    <b class="name_st">Project title</b>
                    <a href="/mynovel/all/write/416999">episode</a>
                </div>
                """
            },
        )
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "create_work_url": "https://novelpia.com/publishing/new",
            },
        )

        client.ensure_work(
            PlatformWorkMetadata(
                title="Project title",
                description="desc",
                genre="12",
            ),
            work_id="",
        )

        self.assertIn(
            ("click_if_present", ".btn_challenge_cancel:visible", "2000"),
            browser.actions,
        )

    def test_ensure_work_requires_genre_before_submission(self):
        from core.platform_clients.novelpia import NovelpiaClient

        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=FakeBrowserSession(),
            platform_config={
                "create_work_url": "https://novelpia.com/publishing/new",
            },
        )

        with self.assertRaises(PlatformError) as context:
            client.ensure_work(
                PlatformWorkMetadata(
                    title="Project title",
                    description="desc",
                    genre="",
                ),
                work_id="",
            )

        self.assertEqual(context.exception.error_type, "requires_user_action")

    def test_ensure_work_requires_completion_redirect(self):
        from core.platform_clients.novelpia import NovelpiaClient

        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=FakeBrowserSession(),
            platform_config={
                "create_work_url": "https://novelpia.com/publishing/new",
            },
        )

        with self.assertRaises(PlatformError) as context:
            client.ensure_work(
                PlatformWorkMetadata(
                    title="Project title",
                    description="desc",
                    genre="1",
                ),
                work_id="",
            )

        self.assertEqual(context.exception.error_type, "retryable")

    def test_ensure_work_prefers_matching_writer_room_entry_over_previous_work(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession(
            click_url="https://novelpia.com/publishing/new_proc",
            page_contents={
                "https://novelpia.com/writer_room": """
                <div class="novel_416704">
                    <a href="/mynovel/all/write/416704">episode</a>
                    <b class="name_st">Older title</b>
                </div>
                <div class="novel_416999">
                    <b class="name_st">Project title</b>
                    <a href="/mynovel/all/write/416999">episode</a>
                </div>
                """
            },
        )
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "create_work_url": "https://novelpia.com/publishing/new",
            },
        )

        result = client.ensure_work(
            PlatformWorkMetadata(
                title="Project title",
                description="desc",
                genre="12",
            ),
            work_id="",
        )

        self.assertEqual(result.work_id, "416999")

    def test_upload_episode_returns_success_payload(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession(click_url="https://novelpia.com/mynovel/all/416704")
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
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
        self.assertEqual(result.episode_id, "416704")

    def test_upload_episode_uses_real_writer_form_selectors(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession(click_url="https://novelpia.com/mynovel/all/416704")
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
            },
        )

        client.upload_episode(
            EpisodeUploadRequest(
                work_id="416704",
                episode_title="Episode 12",
                content="body",
            )
        )

        self.assertEqual(
            browser.actions[:7],
            [
                ("goto", "https://novelpia.com/mynovel/all/write/416704", ""),
                ("fill", "#content_subject", "Episode 12"),
                ("fill", ".note-editable", "body"),
                ("select_option", "#content_cate", "24"),
                ("click_if_present", ".event-plus-close:visible", "2000"),
                ("click_if_present", "p.later-close:visible", "1000"),
                ("click", ".btn.btn-block.btn-primary.s_inv", ""),
            ],
        )

    def test_upload_episode_prefers_request_work_id_over_stale_fixed_editor_url(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession(click_url="https://novelpia.com/mynovel/all/999999")
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/416704",
            },
        )

        client.upload_episode(
            EpisodeUploadRequest(
                work_id="999999",
                episode_title="Episode 12",
                content="body",
            )
        )

        self.assertEqual(
            browser.actions[0],
            ("goto", "https://novelpia.com/mynovel/all/write/999999", ""),
        )

    def test_upload_episode_sets_private_category_when_requested(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession(click_url="https://novelpia.com/mynovel/all/416704")
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
            },
        )

        client.upload_episode(
            EpisodeUploadRequest(
                work_id="416704",
                episode_title="Episode 12",
                content="body",
                visibility="private",
            )
        )

        self.assertIn(
            ("select_option", "#content_cate", "5"),
            browser.actions,
        )

    def test_set_publish_options_accepts_immediate_private_mode(self):
        from core.platform_clients.novelpia import NovelpiaClient

        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=FakeBrowserSession(),
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
            },
        )

        result = client.set_publish_options(
            {
                "publish_mode": "immediate",
                "visibility": "private",
                "reserved_at": None,
            }
        )

        self.assertTrue(result.success)

    def test_set_publish_options_accepts_reserved_mode_with_reserved_at(self):
        from core.platform_clients.novelpia import NovelpiaClient

        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=FakeBrowserSession(),
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
            },
        )

        result = client.set_publish_options(
            {
                "publish_mode": "reserved",
                "visibility": "private",
                "reserved_at": "2026-03-16T21:00:00+09:00",
            }
        )

        self.assertTrue(result.success)

    def test_set_publish_options_requires_reserved_at_for_reserved_mode(self):
        from core.platform_clients.novelpia import NovelpiaClient

        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=FakeBrowserSession(),
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
            },
        )

        with self.assertRaises(PlatformError) as context:
            client.set_publish_options(
                {
                    "publish_mode": "reserved",
                    "visibility": "private",
                    "reserved_at": None,
                }
            )

        self.assertEqual(context.exception.error_type, "requires_user_action")

    def test_supported_publish_modes_include_reserved(self):
        from core.platform_clients.novelpia import NovelpiaClient

        self.assertEqual(NovelpiaClient.supported_publish_modes(), ("immediate", "reserved"))

    def test_smoke_check_editor_succeeds_when_required_fields_exist(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession(
            present_selectors={
                "#content_subject",
                ".note-editable",
                "#content_cate",
            }
        )
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
            },
        )

        result = client.smoke_check_editor("416704")

        self.assertTrue(result.success)
        self.assertEqual(result.work_id, "416704")
        self.assertEqual(
            browser.actions[:4],
            [
                ("goto", "https://novelpia.com/mynovel/all/write/416704", ""),
                ("has_selector", "#content_subject", "3000"),
                ("has_selector", ".note-editable", "3000"),
                ("has_selector", "#content_cate", "3000"),
            ],
        )

    def test_upload_episode_uses_pending_publish_options_for_private_visibility(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession(click_url="https://novelpia.com/mynovel/all/416704")
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
            },
        )

        client.set_publish_options(
            {
                "publish_mode": "immediate",
                "visibility": "private",
                "reserved_at": None,
            }
        )
        client.upload_episode(
            EpisodeUploadRequest(
                work_id="416704",
                episode_title="Episode 12",
                content="body",
                visibility="public",
            )
        )

        self.assertIn(
            ("select_option", "#content_cate", "5"),
            browser.actions,
        )

    def test_upload_episode_applies_reserved_publish_controls_when_configured(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession(click_url="https://novelpia.com/mynovel/all/416704?scheduled=1")
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
                "selectors": {
                    "episode_publish_mode_reserved": "#reserve-mode",
                    "episode_reserved_date": "#reserve-date",
                    "episode_reserved_time": "#reserve-time",
                },
            },
        )

        client.set_publish_options(
            {
                "publish_mode": "reserved",
                "visibility": "private",
                "reserved_at": "2026-03-16T21:30:00+09:00",
            }
        )
        client.upload_episode(
            EpisodeUploadRequest(
                work_id="416704",
                episode_title="Episode 12",
                content="body",
                visibility="public",
            )
        )

        self.assertIn(("click", "#reserve-mode", ""), browser.actions)
        self.assertIn(("fill", "#reserve-date", "2026-03-16"), browser.actions)
        self.assertIn(("fill", "#reserve-time", "21:30"), browser.actions)

    def test_upload_episode_dismisses_event_overlay_when_present(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession(
            click_url="https://novelpia.com/mynovel/all/416704",
            present_selectors={".event-plus-close:visible"},
        )
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
            },
        )

        client.upload_episode(
            EpisodeUploadRequest(
                work_id="416704",
                episode_title="Episode 12",
                content="body",
            )
        )

        self.assertIn(
            ("click_if_present", ".event-plus-close:visible", "2000"),
            browser.actions,
        )

    def test_upload_episode_waits_for_viewer_redirect_before_returning_episode_id(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession(
            click_urls=[
                "https://novelpia.com/mynovel/all/write_proc",
                "https://novelpia.com/viewer/5471585",
            ]
        )
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
            },
        )

        result = client.upload_episode(
            EpisodeUploadRequest(
                work_id="416704",
                episode_title="Episode 12",
                content="body",
            )
        )

        self.assertEqual(result.episode_id, "5471585")
        self.assertIn(
            ("wait_for_url_change", "https://novelpia.com/mynovel/all/write/416704", "10000"),
            browser.actions,
        )
        self.assertIn(
            ("wait_for_url_change", "https://novelpia.com/mynovel/all/write_proc", "10000"),
            browser.actions,
        )

    def test_verify_publication_succeeds_for_viewer_url(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession()
        browser.current_url = "https://novelpia.com/viewer/5471585"
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
            },
        )

        result = client.verify_publication({"work_id": "416704", "episode_id": "5471585"})

        self.assertTrue(result.success)
        self.assertEqual(result.episode_id, "5471585")

    def test_verify_publication_fails_retryably_for_editor_or_write_proc_url(self):
        from core.platform_clients.novelpia import NovelpiaClient

        editor_client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=FakeBrowserSession(),
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
            },
        )
        editor_client._browser_session.current_url = "https://novelpia.com/mynovel/all/write/416704"

        with self.assertRaises(PlatformError) as editor_context:
            editor_client.verify_publication({"work_id": "416704", "episode_id": "5471585"})

        self.assertEqual(editor_context.exception.error_type, "retryable")

        proc_client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=FakeBrowserSession(),
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
            },
        )
        proc_client._browser_session.current_url = "https://novelpia.com/mynovel/all/write_proc"

        with self.assertRaises(PlatformError) as proc_context:
            proc_client.verify_publication({"work_id": "416704", "episode_id": "5471585"})

        self.assertEqual(proc_context.exception.error_type, "retryable")

    def test_verify_publication_returns_scheduled_for_reserved_confirmation_url(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession()
        browser.current_url = "https://novelpia.com/mynovel/all/416704?scheduled=1"
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
            },
        )

        result = client.verify_publication(
            {
                "work_id": "416704",
                "episode_id": "",
                "publish_mode": "reserved",
                "reserved_at": "2026-03-16T21:00:00+09:00",
            }
        )

        self.assertTrue(result.success)
        self.assertEqual(result.status, "scheduled")

    def test_verify_publication_returns_done_for_reserved_follow_up_listing_match(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession(
            page_contents={
                "https://novelpia.com/mynovel/all/416704": "<div>Episode 12</div>",
            }
        )
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
            },
        )

        result = client.verify_publication(
            {
                "work_id": "416704",
                "episode_id": "",
                "episode_title": "Episode 12",
                "publish_mode": "reserved",
                "reserved_at": "2026-03-16T21:00:00+09:00",
                "verification_mode": "scheduled_follow_up",
            }
        )

        self.assertTrue(result.success)
        self.assertEqual(result.status, "done")
        self.assertIn(("goto", "https://novelpia.com/mynovel/all/416704", ""), browser.actions)

    def test_verify_publication_raises_retryable_when_reserved_follow_up_title_is_missing(self):
        from core.platform_clients.novelpia import NovelpiaClient

        browser = FakeBrowserSession(
            page_contents={
                "https://novelpia.com/mynovel/all/416704": "<div>Other episode</div>",
            }
        )
        client = NovelpiaClient(
            username="writer-id",
            password="secret",
            browser_session=browser,
            platform_config={
                "upload_url_template": "https://novelpia.com/mynovel/all/write/{work_id}",
            },
        )

        with self.assertRaises(PlatformError) as context:
            client.verify_publication(
                {
                    "work_id": "416704",
                    "episode_id": "",
                    "episode_title": "Episode 12",
                    "publish_mode": "reserved",
                    "reserved_at": "2026-03-16T21:00:00+09:00",
                    "verification_mode": "scheduled_follow_up",
                }
            )

        self.assertEqual(context.exception.error_type, "retryable")


if __name__ == "__main__":
    unittest.main()
