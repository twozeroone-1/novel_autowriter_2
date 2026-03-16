import unittest

from core.platform_clients.base import PlatformActionResult, PlatformError


class FakeSmokeClient:
    def __init__(
        self,
        *,
        platform_name: str = "",
        username: str,
        password: str,
        platform_config: dict | None = None,
        headless: bool = True,
        fail_on_login: PlatformError | None = None,
        fail_on_editor: PlatformError | None = None,
    ):
        self.username = username
        self.password = password
        self.platform_config = platform_config or {}
        self.headless = headless
        self.fail_on_login = fail_on_login
        self.fail_on_editor = fail_on_editor
        self.actions: list[tuple[str, str]] = []

    def login(self) -> PlatformActionResult:
        self.actions.append(("login", ""))
        if self.fail_on_login is not None:
            raise self.fail_on_login
        return PlatformActionResult(status="done", success=True)

    def smoke_check_editor(self, work_id: str) -> PlatformActionResult:
        self.actions.append(("smoke_check_editor", work_id))
        if self.fail_on_editor is not None:
            raise self.fail_on_editor
        return PlatformActionResult(status="done", success=True, work_id=work_id)

    def close(self) -> None:
        self.actions.append(("close", ""))


class TestPublishingSmoke(unittest.TestCase):
    def test_run_publishing_smoke_reports_success_for_ready_platform(self):
        from core.publishing_smoke import run_publishing_smoke

        created_clients: dict[str, FakeSmokeClient] = {}

        def client_factory(**kwargs):
            client = FakeSmokeClient(**kwargs)
            created_clients[kwargs["platform_name"]] = client
            return client

        result = run_publishing_smoke(
            project_name="sample",
            config={
                "browser": {"headless": True},
                "platforms": {
                    "munpia": {
                        "name": "munpia",
                        "enabled": True,
                        "work_id": "work-1",
                    }
                },
            },
            credential_loader=lambda _project, _platform: {"username": "writer-id", "password": "secret"},
            client_factory=client_factory,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["checked_platforms"], ["munpia"])
        self.assertEqual(result["platform_results"]["munpia"]["status"], "done")
        self.assertEqual(created_clients["munpia"].actions[:2], [("login", ""), ("smoke_check_editor", "work-1")])

    def test_run_publishing_smoke_fails_when_credentials_are_missing(self):
        from core.publishing_smoke import run_publishing_smoke

        result = run_publishing_smoke(
            project_name="sample",
            config={
                "browser": {"headless": True},
                "platforms": {
                    "munpia": {
                        "enabled": True,
                        "work_id": "work-1",
                    }
                },
            },
            credential_loader=lambda _project, _platform: {"username": "", "password": ""},
            client_factory=lambda **kwargs: FakeSmokeClient(**kwargs),
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["platform_results"]["munpia"]["error_type"], "requires_user_action")

    def test_run_publishing_smoke_fails_when_work_id_is_missing(self):
        from core.publishing_smoke import run_publishing_smoke

        result = run_publishing_smoke(
            project_name="sample",
            config={
                "browser": {"headless": True},
                "platforms": {
                    "novelpia": {
                        "enabled": True,
                        "work_id": "",
                    }
                },
            },
            credential_loader=lambda _project, _platform: {"username": "writer-id", "password": "secret"},
            client_factory=lambda **kwargs: FakeSmokeClient(**kwargs),
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["platform_results"]["novelpia"]["error_type"], "requires_user_action")

    def test_run_publishing_smoke_fails_when_explicit_platform_is_disabled(self):
        from core.publishing_smoke import run_publishing_smoke

        result = run_publishing_smoke(
            project_name="sample",
            platforms=["munpia"],
            config={
                "browser": {"headless": True},
                "platforms": {
                    "munpia": {
                        "enabled": False,
                        "work_id": "work-1",
                    }
                },
            },
            credential_loader=lambda _project, _platform: {"username": "writer-id", "password": "secret"},
            client_factory=lambda **kwargs: FakeSmokeClient(**kwargs),
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["platform_results"]["munpia"]["error_type"], "requires_user_action")

    def test_run_publishing_smoke_respects_explicit_platform_filter(self):
        from core.publishing_smoke import run_publishing_smoke

        seen_platforms: list[str] = []

        def client_factory(**kwargs):
            seen_platforms.append(kwargs["platform_name"])
            return FakeSmokeClient(**kwargs)

        result = run_publishing_smoke(
            project_name="sample",
            platforms=["novelpia"],
            config={
                "browser": {"headless": False},
                "platforms": {
                    "munpia": {
                        "name": "munpia",
                        "enabled": True,
                        "work_id": "work-1",
                    },
                    "novelpia": {
                        "name": "novelpia",
                        "enabled": True,
                        "work_id": "work-2",
                    },
                },
            },
            credential_loader=lambda _project, _platform: {"username": "writer-id", "password": "secret"},
            client_factory=client_factory,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["checked_platforms"], ["novelpia"])
        self.assertEqual(seen_platforms, ["novelpia"])


if __name__ == "__main__":
    unittest.main()
