import unittest
from pathlib import Path
from unittest.mock import patch


class TestMunpiaSessionLauncher(unittest.TestCase):
    def test_build_bootstrap_command_points_to_script(self):
        from core.munpia_session_launcher import build_bootstrap_command

        command = build_bootstrap_command(project_name="2", repo_root=Path("/mnt/c/Users/W/novel_autowriter_2"))

        self.assertIn("python3 scripts/bootstrap_munpia_session.py 2", command)
        self.assertIn('cd "/mnt/c/Users/W/novel_autowriter_2"', command)

    def test_launch_bootstrap_uses_windows_terminal_command(self):
        launched = {}

        def fake_popen(args, **kwargs):
            launched["args"] = args
            launched["kwargs"] = kwargs
            class Dummy:
                pass
            return Dummy()

        with patch("core.munpia_session_launcher.subprocess.Popen", side_effect=fake_popen):
            from core.munpia_session_launcher import launch_bootstrap_terminal

            ok, message = launch_bootstrap_terminal(
                project_name="2",
                repo_root=Path("/mnt/c/Users/W/novel_autowriter_2"),
            )

        self.assertTrue(ok)
        self.assertIn("새 터미널", message)
        self.assertEqual(launched["args"][:3], ["cmd.exe", "/c", "start"])
