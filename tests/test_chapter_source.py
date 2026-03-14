import importlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.episode_artifact_store import EpisodeArtifactStore


class TestChapterSource(unittest.TestCase):
    def test_load_chapter_source_reads_markdown_file(self):
        spec = importlib.util.find_spec("core.chapter_source")
        self.assertIsNotNone(spec, "core.chapter_source should exist")
        module = importlib.import_module("core.chapter_source")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "12화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            chapter_path.write_text("# 12화. 계약의 대가\n\n본문입니다.", encoding="utf-8")

            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir):
                payload = module.load_chapter_source("sample", "chapters/12화.md")

        self.assertEqual(payload["title"], "12화. 계약의 대가")
        self.assertIn("본문입니다.", payload["content"])
        self.assertEqual(payload["path"], chapter_path)

    def test_load_chapter_source_rejects_missing_file(self):
        module = importlib.import_module("core.chapter_source")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"

            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir):
                with self.assertRaises(FileNotFoundError):
                    module.load_chapter_source("sample", "chapters/missing.md")

    def test_load_chapter_source_falls_back_to_filename_when_heading_missing(self):
        module = importlib.import_module("core.chapter_source")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "13화_임시.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            chapter_path.write_text("제목 헤더가 없는 본문", encoding="utf-8")

            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir):
                payload = module.load_chapter_source("sample", "chapters/13화_임시.md")

        self.assertEqual(payload["title"], "13화_임시")

    def test_load_chapter_source_prefers_publishable_episode_artifact(self):
        module = importlib.import_module("core.chapter_source")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "12화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            chapter_path.write_text("# 12화. 레거시\n\n레거시 본문", encoding="utf-8")

            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir), patch(
                "core.episode_artifact_store.DATA_PROJECTS_DIR", projects_dir
            ):
                store = EpisodeArtifactStore(project_name="sample")
                store.create_draft(title="12화. 아티팩트", content="# 12화. 아티팩트\n\n아티팩트 본문", episode_id="ep_012")
                store.promote_to_publishable("ep_012")

                payload = module.load_chapter_source("sample", "chapters/12화.md", episode_id="ep_012")

        self.assertEqual(payload["title"], "12화. 아티팩트")
        self.assertIn("아티팩트 본문", payload["content"])
        self.assertEqual(payload["episode_id"], "ep_012")
        self.assertEqual(payload["artifact_status"], "publishable")

    def test_load_chapter_source_includes_stored_canon_update_for_episode_artifact(self):
        module = importlib.import_module("core.chapter_source")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "15화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            chapter_path.write_text("# 15화. 레거시\n\n레거시 본문", encoding="utf-8")

            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir), patch(
                "core.episode_artifact_store.DATA_PROJECTS_DIR", projects_dir
            ):
                store = EpisodeArtifactStore(project_name="sample")
                store.create_draft(title="15화. 아티팩트", content="# 15화. 아티팩트\n\n아티팩트 본문", episode_id="ep_015")
                store.promote_to_publishable("ep_015")
                store.save_canon_update("ep_015", {"people": {"lead": {"mood": "alert"}}})

                payload = module.load_chapter_source("sample", "chapters/15화.md", episode_id="ep_015")

        self.assertEqual(payload["canon_update"]["people"]["lead"]["mood"], "alert")

    def test_load_chapter_source_falls_back_to_legacy_chapter_path_when_artifact_missing(self):
        module = importlib.import_module("core.chapter_source")

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "14화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            chapter_path.write_text("# 14화. 레거시만 존재\n\n레거시 본문", encoding="utf-8")

            with patch.object(module, "DATA_PROJECTS_DIR", projects_dir), patch(
                "core.episode_artifact_store.DATA_PROJECTS_DIR", projects_dir
            ):
                payload = module.load_chapter_source("sample", "chapters/14화.md", episode_id="ep_014")

        self.assertEqual(payload["title"], "14화. 레거시만 존재")
        self.assertIn("레거시 본문", payload["content"])
        self.assertEqual(payload["episode_id"], "ep_014")
        self.assertEqual(payload["artifact_status"], "legacy")


if __name__ == "__main__":
    unittest.main()
