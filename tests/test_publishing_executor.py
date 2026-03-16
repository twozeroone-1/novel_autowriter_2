import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.platform_clients.base import PlatformActionResult, PlatformError


class FakeClient:
    def __init__(self, *, created_work_id: str = "", episode_id: str = "episode-1"):
        self.created_work_id = created_work_id
        self.episode_id = episode_id
        self.calls = []

    def login(self):
        self.calls.append(("login",))
        return PlatformActionResult(status="done", success=True)

    def ensure_work(self, metadata, work_id: str = ""):
        self.calls.append(("ensure_work", metadata.title, work_id))
        if work_id:
            return PlatformActionResult(status="done", success=True, work_id=work_id)
        return PlatformActionResult(status="done", success=True, work_id=self.created_work_id or "created-work")

    def upload_episode(self, request):
        self.calls.append(("upload_episode", request.work_id, request.episode_title, request.content))
        return PlatformActionResult(
            status="done",
            success=True,
            work_id=request.work_id,
            episode_id=self.episode_id,
        )

    def close(self):
        self.calls.append(("close",))


class TestPublishingExecutor(unittest.TestCase):
    def test_publish_job_uses_publish_packager_output_for_upload_payload(self):
        from core.publishing_executor import PublishingExecutor

        fake_client = FakeClient()
        packager_report = {
            "source": {"title": "12화. 계약의 대가", "episode_id": "", "artifact_status": "legacy"},
            "packages": {
                "munpia": {
                    "work_id": "work-1",
                    "work_metadata": {
                        "title": "Project title",
                        "description": "desc",
                        "genre": "fantasy",
                        "age_grade": "general",
                        "cover_path": "",
                    },
                    "upload_request": {
                        "episode_title": "Packaged Episode 12",
                        "content": "# 12화. 계약의 대가\n\n패키저 본문",
                        "publish_mode": "immediate",
                        "visibility": "public",
                        "reserved_at": None,
                    },
                    "expected_publication": {
                        "episode_title": "Packaged Episode 12",
                        "publish_mode": "immediate",
                        "visibility": "public",
                        "reserved_at": None,
                    },
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "12화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            chapter_path.write_text("# 12화. 계약의 대가\n\n본문", encoding="utf-8")

            with patch("core.chapter_source.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.publishing_executor.build_publish_packages",
                return_value=packager_report,
            ) as build_publish_packages:
                executor = PublishingExecutor(
                    project_name="sample",
                    credential_loader=lambda project_name, platform_name: {"username": "id", "password": "pw"},
                    client_factory=lambda **kwargs: fake_client,
                )
                result = executor.publish_job(
                    job={
                        "chapter_title": "Episode 12",
                        "source_path": "chapters/12화.md",
                        "targets": {
                            "munpia": {
                                "selected": True,
                                "work_id": "work-1",
                            }
                        },
                    },
                    config={
                        "browser": {"headless": True},
                        "platforms": {
                            "munpia": {"enabled": True, "work_id": ""},
                        },
                    },
                )

        build_publish_packages.assert_called_once()
        self.assertIn(("upload_episode", "work-1", "Packaged Episode 12", "# 12화. 계약의 대가\n\n패키저 본문"), fake_client.calls)
        self.assertEqual(result["packager_report"], packager_report)

    def test_publish_job_uses_existing_work_id_and_uploads_selected_platform(self):
        from core.publishing_executor import PublishingExecutor

        fake_client = FakeClient()

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "12화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            chapter_path.write_text("# 12화. 계약의 대가\n\n본문", encoding="utf-8")

            with patch("core.chapter_source.DATA_PROJECTS_DIR", projects_dir):
                executor = PublishingExecutor(
                    project_name="sample",
                    credential_loader=lambda project_name, platform_name: {"username": "id", "password": "pw"},
                    client_factory=lambda **kwargs: fake_client,
                )
                result = executor.publish_job(
                    job={
                        "chapter_title": "Episode 12",
                        "source_path": "chapters/12화.md",
                        "targets": {
                            "munpia": {
                                "selected": True,
                                "work_id": "work-1",
                                "episode_title": "Episode 12",
                            }
                        },
                    },
                    config={
                        "browser": {"headless": True},
                        "platforms": {
                            "munpia": {"enabled": True, "work_id": ""},
                        },
                    },
                )

        self.assertTrue(result["platform_results"]["munpia"]["success"])
        self.assertEqual(result["platform_results"]["munpia"]["work_id"], "work-1")
        self.assertIn(("upload_episode", "work-1", "Episode 12", "# 12화. 계약의 대가\n\n본문"), fake_client.calls)

    def test_publish_job_creates_work_when_no_work_id_exists(self):
        from core.publishing_executor import PublishingExecutor

        fake_client = FakeClient(created_work_id="created-work")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "12화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            chapter_path.write_text("# 12화. 계약의 대가\n\n본문", encoding="utf-8")

            with patch("core.chapter_source.DATA_PROJECTS_DIR", projects_dir):
                executor = PublishingExecutor(
                    project_name="sample",
                    credential_loader=lambda project_name, platform_name: {"username": "id", "password": "pw"},
                    client_factory=lambda **kwargs: fake_client,
                )
                result = executor.publish_job(
                    job={
                        "chapter_title": "Episode 12",
                        "source_path": "chapters/12화.md",
                        "targets": {
                            "munpia": {
                                "selected": True,
                                "episode_title": "Episode 12",
                            }
                        },
                    },
                    config={
                        "browser": {"headless": True},
                        "platforms": {
                            "munpia": {
                                "enabled": True,
                                "work_id": "",
                                "work_title": "Project title",
                                "work_description": "desc",
                                "genre": "fantasy",
                                "default_age_grade": "general",
                            },
                        },
                    },
                )

        self.assertEqual(result["platform_results"]["munpia"]["work_id"], "created-work")
        self.assertEqual(result["platform_config_updates"]["munpia"]["work_id"], "created-work")
        self.assertIn(("ensure_work", "Project title", ""), fake_client.calls)

    def test_publish_job_marks_missing_credentials_as_user_action(self):
        from core.publishing_executor import PublishingExecutor

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "12화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            chapter_path.write_text("# 12화. 계약의 대가\n\n본문", encoding="utf-8")

            with patch("core.chapter_source.DATA_PROJECTS_DIR", projects_dir):
                executor = PublishingExecutor(
                    project_name="sample",
                    credential_loader=lambda project_name, platform_name: {"username": "", "password": ""},
                    client_factory=lambda **kwargs: FakeClient(),
                )
                result = executor.publish_job(
                    job={
                        "chapter_title": "Episode 12",
                        "source_path": "chapters/12화.md",
                        "targets": {
                            "munpia": {
                                "selected": True,
                            }
                        },
                    },
                    config={
                        "browser": {"headless": True},
                        "platforms": {
                            "munpia": {"enabled": True, "work_id": ""},
                        },
                    },
                )

        self.assertFalse(result["platform_results"]["munpia"]["success"])
        self.assertEqual(result["platform_results"]["munpia"]["error_type"], "requires_user_action")

    def test_publish_job_prefers_episode_artifact_when_episode_id_is_present(self):
        from core.publishing_executor import PublishingExecutor
        from core.episode_artifact_store import EpisodeArtifactStore

        fake_client = FakeClient()

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "12화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            chapter_path.write_text("# 12화. 레거시\n\n레거시 본문", encoding="utf-8")

            with patch("core.chapter_source.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.episode_artifact_store.DATA_PROJECTS_DIR", projects_dir
            ):
                store = EpisodeArtifactStore(project_name="sample")
                store.create_draft(title="12화. 아티팩트", content="# 12화. 아티팩트\n\n아티팩트 본문", episode_id="ep_012")
                store.promote_to_publishable("ep_012")

                executor = PublishingExecutor(
                    project_name="sample",
                    credential_loader=lambda project_name, platform_name: {"username": "id", "password": "pw"},
                    client_factory=lambda **kwargs: fake_client,
                )
                result = executor.publish_job(
                    job={
                        "chapter_title": "Episode 12",
                        "source_path": "chapters/12화.md",
                        "episode_id": "ep_012",
                        "targets": {
                            "munpia": {
                                "selected": True,
                                "work_id": "work-1",
                                "episode_title": "Episode 12",
                            }
                        },
                    },
                    config={
                        "browser": {"headless": True},
                        "platforms": {
                            "munpia": {"enabled": True, "work_id": ""},
                        },
                    },
                )

        self.assertEqual(result["source"]["episode_id"], "ep_012")
        self.assertEqual(result["source"]["artifact_status"], "publishable")
        self.assertIn(("upload_episode", "work-1", "Episode 12", "# 12화. 아티팩트\n\n아티팩트 본문"), fake_client.calls)

    def test_publish_job_prefers_source_override_when_present(self):
        from core.publishing_executor import PublishingExecutor

        fake_client = FakeClient()

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "12화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            chapter_path.write_text("# 12화. 계약의 대가\n\n원본 본문", encoding="utf-8")

            with patch("core.chapter_source.DATA_PROJECTS_DIR", projects_dir):
                executor = PublishingExecutor(
                    project_name="sample",
                    credential_loader=lambda project_name, platform_name: {"username": "id", "password": "pw"},
                    client_factory=lambda **kwargs: fake_client,
                )
                result = executor.publish_job(
                    job={
                        "chapter_title": "Episode 12",
                        "source_path": "chapters/12화.md",
                        "source_override": {
                            "title": "12화. 계약의 대가",
                            "content": "# 12화. 계약의 대가\n\n수정된 본문",
                        },
                        "targets": {
                            "munpia": {
                                "selected": True,
                                "work_id": "work-1",
                                "episode_title": "Episode 12",
                            }
                        },
                    },
                    config={
                        "browser": {"headless": True},
                        "platforms": {
                            "munpia": {"enabled": True, "work_id": ""},
                        },
                    },
                )

        self.assertEqual(result["source"]["content"], "# 12화. 계약의 대가\n\n수정된 본문")
        self.assertIn(("upload_episode", "work-1", "Episode 12", "# 12화. 계약의 대가\n\n수정된 본문"), fake_client.calls)


if __name__ == "__main__":
    unittest.main()
