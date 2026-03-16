import importlib
import importlib.util
import unittest


def _source_payload() -> dict:
    return {
        "title": "12화. 계약의 대가",
        "content": "# 12화. 계약의 대가\n\n본문입니다.",
        "episode_id": "ep_012",
        "artifact_status": "publishable",
    }


class TestPublishPackager(unittest.TestCase):
    def _load_module(self):
        spec = importlib.util.find_spec("core.publish_packager")
        self.assertIsNotNone(spec, "core.publish_packager should exist")
        return importlib.import_module("core.publish_packager")

    def test_build_publish_packages_builds_selected_target_package(self):
        module = self._load_module()

        report = module.build_publish_packages(
            project_name="sample",
            source_payload=_source_payload(),
            job={
                "chapter_title": "Episode 12",
                "targets": {
                    "munpia": {
                        "selected": True,
                        "work_id": "work-1",
                        "episode_title": "Episode 12",
                    }
                },
            },
            config={
                "platforms": {
                    "munpia": {
                        "work_title": "Project title",
                        "work_description": "desc",
                        "genre": "fantasy",
                        "default_age_grade": "general",
                    }
                }
            },
        )

        package = report["packages"]["munpia"]
        self.assertEqual(package["work_id"], "work-1")
        self.assertEqual(package["work_metadata"]["title"], "Project title")
        self.assertEqual(package["upload_request"]["episode_title"], "Episode 12")
        self.assertEqual(package["upload_request"]["content"], "# 12화. 계약의 대가\n\n본문입니다.")

    def test_build_publish_packages_falls_back_from_target_title_to_job_and_source(self):
        module = self._load_module()

        job_title_report = module.build_publish_packages(
            project_name="sample",
            source_payload=_source_payload(),
            job={
                "chapter_title": "Job Episode 12",
                "targets": {"munpia": {"selected": True}},
            },
            config={"platforms": {"munpia": {}}},
        )
        source_title_report = module.build_publish_packages(
            project_name="sample",
            source_payload=_source_payload(),
            job={
                "chapter_title": "",
                "targets": {"munpia": {"selected": True}},
            },
            config={"platforms": {"munpia": {}}},
        )

        self.assertEqual(job_title_report["packages"]["munpia"]["upload_request"]["episode_title"], "Job Episode 12")
        self.assertEqual(source_title_report["packages"]["munpia"]["upload_request"]["episode_title"], "12화. 계약의 대가")

    def test_build_publish_packages_preserves_publish_options_and_project_title_fallback(self):
        module = self._load_module()

        report = module.build_publish_packages(
            project_name="sample-project",
            source_payload=_source_payload(),
            job={
                "chapter_title": "Episode 12",
                "targets": {
                    "novelpia": {
                        "selected": True,
                        "publish_mode": "reserved",
                        "visibility": "private",
                        "reserved_at": "2026-03-16T12:00:00+09:00",
                    }
                },
            },
            config={"platforms": {"novelpia": {}}},
        )

        package = report["packages"]["novelpia"]
        self.assertEqual(package["work_metadata"]["title"], "sample-project")
        self.assertEqual(package["upload_request"]["publish_mode"], "reserved")
        self.assertEqual(package["upload_request"]["visibility"], "private")
        self.assertEqual(package["upload_request"]["reserved_at"], "2026-03-16T12:00:00+09:00")
        self.assertEqual(package["expected_publication"]["publish_mode"], "reserved")


if __name__ == "__main__":
    unittest.main()
