import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.release_policy_store as release_policy_store_module
from core.release_policy_store import ReleasePolicyStore


class TestReleasePolicyStore(unittest.TestCase):
    def test_load_policy_returns_platform_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(release_policy_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = ReleasePolicyStore(project_name="sample")

                policy = store.load()

                self.assertIn("global", policy)
                self.assertIn("platforms", policy)
                self.assertIn("munpia", policy["platforms"])
                self.assertIn("novelpia", policy["platforms"])
                self.assertEqual(policy["global"]["max_daily_releases"], 1)

    def test_save_policy_round_trips_platform_overrides(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(release_policy_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)):
                store = ReleasePolicyStore(project_name="sample")

                store.save(
                    {
                        "global": {
                            "max_daily_releases": 2,
                            "cooldown_failures": 3,
                        },
                        "platforms": {
                            "munpia": {
                                "enabled": True,
                                "default_times": ["07:00", "19:00"],
                            }
                        },
                    }
                )

                policy = store.load()

                self.assertEqual(policy["global"]["max_daily_releases"], 2)
                self.assertEqual(policy["global"]["cooldown_failures"], 3)
                self.assertTrue(policy["platforms"]["munpia"]["enabled"])
                self.assertEqual(policy["platforms"]["munpia"]["default_times"], ["07:00", "19:00"])
                self.assertIn("novelpia", policy["platforms"])


if __name__ == "__main__":
    unittest.main()
