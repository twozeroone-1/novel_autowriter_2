import unittest


from core.publishing_readiness import build_publishing_readiness_snapshot


class TestPublishingReadiness(unittest.TestCase):
    def test_snapshot_marks_platform_ready_when_credentials_and_mapping_exist(self):
        snapshot = build_publishing_readiness_snapshot(
            project_name="sample",
            config={
                "platforms": {
                    "novelpia": {
                        "enabled": True,
                        "work_id": "416704",
                        "upload_url_template": "https://example.test/upload/{work_id}",
                    }
                }
            },
            credential_loader=lambda _project, _platform: {"username": "writer", "password": "secret"},
        )

        self.assertEqual(snapshot["enabled_platform_count"], 1)
        self.assertEqual(snapshot["ready_platform_count"], 1)
        self.assertFalse(snapshot["blockers"])
        self.assertTrue(snapshot["platform_rows"][1]["ready"])

    def test_snapshot_reports_missing_credentials_and_mapping(self):
        snapshot = build_publishing_readiness_snapshot(
            project_name="sample",
            config={
                "platforms": {
                    "munpia": {
                        "enabled": True,
                        "work_id": "",
                        "upload_url_template": "",
                    }
                }
            },
            credential_loader=lambda _project, _platform: {"username": "", "password": ""},
        )

        self.assertFalse(snapshot["platform_rows"][0]["ready"])
        self.assertIn("문피아 계정이 설정되지 않았습니다.", snapshot["blockers"])
        self.assertIn("문피아 work_id가 비어 있습니다.", snapshot["blockers"])
        self.assertIn("문피아 업로드 URL이 비어 있습니다.", snapshot["blockers"])
        self.assertIn("플랫폼 계정을 keyring 또는 env fallback으로 설정하세요.", snapshot["recommended_actions"])
        self.assertIn("플랫폼 작품 매핑(work_id / 업로드 URL)을 채우세요.", snapshot["recommended_actions"])

    def test_snapshot_keeps_disabled_platform_out_of_setup_blockers(self):
        snapshot = build_publishing_readiness_snapshot(
            project_name="sample",
            config={
                "platforms": {
                    "munpia": {
                        "enabled": False,
                        "work_id": "",
                        "upload_url_template": "",
                    }
                }
            },
            credential_loader=lambda _project, _platform: {"username": "", "password": ""},
        )

        self.assertEqual(snapshot["enabled_platform_count"], 0)
        self.assertFalse(snapshot["platform_rows"][0]["ready"])
        self.assertNotIn("문피아 계정이 설정되지 않았습니다.", snapshot["blockers"])
        self.assertEqual(snapshot["recommended_actions"][0], "외부 플랫폼 업로드에서 업로드 플랫폼을 활성화하세요.")


if __name__ == "__main__":
    unittest.main()
