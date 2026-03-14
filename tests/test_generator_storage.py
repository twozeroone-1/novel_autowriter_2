import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.context as context_module
import core.episode_artifact_store as episode_artifact_store_module
from core.generator import Generator


class TestGeneratorStorage(unittest.TestCase):
    def test_build_output_path_sanitizes_title(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                generator = Generator(project_name="sample")

                output_path = generator.build_output_path('  <제목>: "1화"?  ', ".md")

                self.assertEqual(output_path.name, "제목 1화.md")

    def test_build_output_path_adds_suffix_for_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                generator = Generator(project_name="sample")
                first_path = generator.build_output_path("중복 제목", ".md")
                first_path.write_text("first", encoding="utf-8")

                second_path = generator.build_output_path("중복 제목", ".md")

                self.assertEqual(second_path.name, "중복 제목_2.md")

    def test_save_chapter_writes_episode_draft_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                with patch.object(episode_artifact_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                    generator = Generator(project_name="sample")

                    filepath = Path(generator.save_chapter("1화. 시작", "본문입니다. " * 30))

                    self.assertTrue(filepath.exists())
                    draft_path = Path(tmpdir) / "sample" / "episodes" / "drafts" / "ep_001.md"
                    manifest_path = Path(tmpdir) / "sample" / "episodes" / "manifests.json"
                    self.assertTrue(draft_path.exists())
                    self.assertTrue(manifest_path.exists())

    def test_save_markdown_document_does_not_create_episode_artifact_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                with patch.object(episode_artifact_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                    generator = Generator(project_name="sample")

                    filepath = Path(
                        generator.save_markdown_document(
                            filename_title="검수리포트",
                            content="리포트 본문",
                        )
                    )

                    self.assertTrue(filepath.exists())
                    manifest_path = Path(tmpdir) / "sample" / "episodes" / "manifests.json"
                    self.assertFalse(manifest_path.exists())


if __name__ == "__main__":
    unittest.main()
