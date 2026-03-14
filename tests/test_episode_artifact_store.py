import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.episode_artifact_store as episode_artifact_store_module
from core.episode_artifact_store import EpisodeArtifactStore


class TestEpisodeArtifactStore(unittest.TestCase):
    def test_create_draft_assigns_episode_id_and_manifest_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(episode_artifact_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = EpisodeArtifactStore(project_name="sample")

                artifact = store.create_draft(title="1화. 시작", content="본문")

                self.assertEqual(artifact["episode_id"], "ep_001")
                self.assertEqual(artifact["sequence"], 1)
                self.assertEqual(artifact["status"], "draft")
                self.assertTrue((store.drafts_dir / "ep_001.md").exists())
                manifest = store.load_manifest()
                self.assertEqual(manifest["episodes"]["ep_001"]["title"], "1화. 시작")

    def test_promote_draft_to_publishable_copies_expected_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(episode_artifact_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = EpisodeArtifactStore(project_name="sample")
                store.create_draft(title="1화. 시작", content="본문")

                artifact = store.promote_to_publishable("ep_001")

                self.assertEqual(artifact["status"], "publishable")
                self.assertTrue((store.publishable_dir / "ep_001.md").exists())
                self.assertEqual(store.load_manifest()["episodes"]["ep_001"]["status"], "publishable")

    def test_mark_published_writes_published_artifact_and_manifest_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(episode_artifact_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = EpisodeArtifactStore(project_name="sample")
                store.create_draft(title="2화. 전개", content="두 번째 본문")
                store.promote_to_publishable("ep_002")

                artifact = store.mark_published("ep_002")

                self.assertEqual(artifact["status"], "published")
                self.assertTrue((store.published_dir / "ep_002.md").exists())
                self.assertEqual(store.load_manifest()["episodes"]["ep_002"]["status"], "published")

    def test_existing_episode_number_is_reused_for_same_episode_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(episode_artifact_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = EpisodeArtifactStore(project_name="sample")
                first = store.create_draft(title="3화. 초안", content="초안")

                second = store.create_draft(title="3화. 수정본", content="수정본", episode_id=first["episode_id"])

                self.assertEqual(first["episode_id"], second["episode_id"])
                self.assertEqual(second["sequence"], 3)
                self.assertEqual(store.load_manifest()["episodes"]["ep_003"]["title"], "3화. 수정본")


if __name__ == "__main__":
    unittest.main()
