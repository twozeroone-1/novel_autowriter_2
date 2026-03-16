import importlib
import importlib.util
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import core.canon_store as canon_store_module
from core.canon_store import CanonStore


class TestPublishingCanon(unittest.TestCase):
    def _load_finalizer(self):
        spec = importlib.util.find_spec("core.publishing_canon")
        self.assertIsNotNone(spec, "core.publishing_canon should exist")
        module = importlib.import_module("core.publishing_canon")
        finalizer = getattr(module, "finalize_publish_canon", None)
        self.assertIsNotNone(finalizer, "finalize_publish_canon should exist")
        return module, finalizer

    def test_finalize_publish_canon_prefers_result_candidate(self):
        _, finalize_publish_canon = self._load_finalizer()

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(canon_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
            store = CanonStore(project_name="sample")
            report = finalize_publish_canon(
                project_name="sample",
                episode_id="ep_012",
                overall_status="done",
                job={"canon_update": {"timeline": ["job"]}},
                result={"canon_update": {"timeline": ["result"]}},
                source_payload={"content": "본문"},
                canon_store=store,
                now=datetime(2026, 3, 16, 21, 0),
            )

            self.assertEqual(report["status"], "applied")
            self.assertEqual(report["source"], "result")
            self.assertIn("result", store.load_current_state()["timeline"])

    def test_finalize_publish_canon_prefers_source_candidate_before_extractor(self):
        module, finalize_publish_canon = self._load_finalizer()

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(canon_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
            store = CanonStore(project_name="sample")
            with patch.object(module, "extract_canon_update", side_effect=AssertionError("extractor should not run")):
                report = finalize_publish_canon(
                    project_name="sample",
                    episode_id="ep_012",
                    overall_status="done",
                    job={},
                    result={},
                    source_payload={"content": "본문", "canon_update": {"timeline": ["source"]}},
                    canon_store=store,
                    now=datetime(2026, 3, 16, 21, 0),
                )

            self.assertEqual(report["status"], "applied")
            self.assertEqual(report["source"], "artifact")
            self.assertIn("source", store.load_current_state()["timeline"])

    def test_finalize_publish_canon_skips_when_publish_failed(self):
        _, finalize_publish_canon = self._load_finalizer()

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(canon_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
            store = CanonStore(project_name="sample")
            report = finalize_publish_canon(
                project_name="sample",
                episode_id="ep_012",
                overall_status="failed",
                job={},
                result={},
                source_payload={"content": "본문"},
                canon_store=store,
                now=datetime(2026, 3, 16, 21, 0),
            )

            self.assertEqual(report["status"], "skipped")
            self.assertEqual(store.load_current_state()["timeline"], [])

    def test_finalize_publish_canon_appends_episode_id_to_candidate_timeline(self):
        _, finalize_publish_canon = self._load_finalizer()

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(canon_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
            store = CanonStore(project_name="sample")
            report = finalize_publish_canon(
                project_name="sample",
                episode_id="ep_021",
                overall_status="done",
                job={},
                result={"canon_update": {"people": {"lead": {"mood": "focused"}}}},
                source_payload={"content": "본문"},
                canon_store=store,
                now=datetime(2026, 3, 16, 21, 0),
            )

            self.assertEqual(report["status"], "applied")
            self.assertEqual(store.load_current_state()["timeline"], ["ep_021"])

    def test_finalize_publish_canon_returns_failed_report_when_extractor_raises(self):
        module, finalize_publish_canon = self._load_finalizer()

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(canon_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
            store = CanonStore(project_name="sample")
            with patch.object(module, "extract_canon_update", side_effect=RuntimeError("canon extract failed")):
                report = finalize_publish_canon(
                    project_name="sample",
                    episode_id="ep_099",
                    overall_status="done",
                    job={},
                    result={},
                    source_payload={"content": "본문"},
                    canon_store=store,
                    now=datetime(2026, 3, 16, 21, 0),
                )

            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["source"], "extractor")
            self.assertEqual(report["error"], "canon extract failed")
            self.assertEqual(store.load_current_state()["timeline"], [])


if __name__ == "__main__":
    unittest.main()
