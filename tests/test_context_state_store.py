import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.context_state_store as context_state_store_module


class TestContextStateStore(unittest.TestCase):
    def test_load_returns_default_state_payload_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_state_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = context_state_store_module.ContextStateStore(project_name="sample")

                payload = store.load()

                self.assertEqual(payload, context_state_store_module.DEFAULT_CONTEXT_STATE)

    def test_save_normalizes_payload_and_round_trips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_state_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = context_state_store_module.ContextStateStore(project_name="sample")

                store.save(
                    {
                        "state": 123,
                        "summary_of_previous": 456,
                    }
                )

                payload = store.load()

                self.assertEqual(
                    payload,
                    {
                        "state": "123",
                        "summary_of_previous": "456",
                    },
                )

    def test_save_preserves_defaults_for_missing_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_state_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = context_state_store_module.ContextStateStore(project_name="sample")

                store.save({"state": "current state"})

                payload = store.load()

                self.assertEqual(payload["state"], "current state")
                self.assertEqual(
                    payload["summary_of_previous"],
                    context_state_store_module.DEFAULT_CONTEXT_STATE["summary_of_previous"],
                )


if __name__ == "__main__":
    unittest.main()
