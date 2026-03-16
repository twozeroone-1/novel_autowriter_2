import json
import subprocess
import sys
import unittest
from pathlib import Path


class TestPublishingSmokeScript(unittest.TestCase):
    def test_script_runs_without_module_import_error(self):
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts" / "publishing_smoke.py"

        completed = subprocess.run(
            [sys.executable, str(script_path), "1", "--platform", "munpia", "--headless", "true"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )

        self.assertNotIn("ModuleNotFoundError", completed.stderr)
        self.assertNotEqual(completed.stdout.strip(), "")
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["project_name"], "1")


if __name__ == "__main__":
    unittest.main()
