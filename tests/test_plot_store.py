import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.plot_store as plot_store_module
from core.plot_store import DEFAULT_PLOT, PlotStore


class TestPlotStore(unittest.TestCase):
    def test_load_returns_default_plot_payload_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(plot_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = PlotStore(project_name="sample")

                payload = store.load()

                self.assertEqual(payload, DEFAULT_PLOT)

    def test_save_normalizes_payload_and_round_trips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(plot_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = PlotStore(project_name="sample")

                store.save(
                    {
                        "plot_outline": 123,
                        "plot_version": 7,
                    }
                )

                payload = store.load()

                self.assertEqual(
                    payload,
                    {
                        "plot_outline": "123",
                        "plot_version": "7",
                    },
                )

    def test_bump_version_increments_from_current_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(plot_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = PlotStore(project_name="sample")
                store.save(
                    {
                        "plot_outline": "old plot",
                        "plot_version": "2",
                    }
                )

                payload = store.bump_version("new plot")

                self.assertEqual(
                    payload,
                    {
                        "plot_outline": "new plot",
                        "plot_version": "3",
                    },
                )
                self.assertEqual(store.load(), payload)


if __name__ == "__main__":
    unittest.main()
