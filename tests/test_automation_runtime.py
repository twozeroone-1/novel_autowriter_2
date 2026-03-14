import importlib
import importlib.util
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from core.automation_store import AutomationStore


class FakeAutomator:
    def __init__(self, *, should_fail: bool = False):
        self.should_fail = should_fail
        self.call_count = 0
        self.before_return = None
        self.apply_calls = []
        self.run_calls = []
        self.result_override = None

    def run_single_cycle(
        self,
        chapter_title: str,
        instruction: str,
        target_length: int,
        include_plot: bool = False,
        plot_strength: str = "balanced",
    ):
        self.call_count += 1
        self.run_calls.append((chapter_title, instruction, target_length, include_plot, plot_strength))
        if self.before_return is not None:
            self.before_return()
        if self.should_fail:
            raise RuntimeError("boom")
        result = {
            "saved_path": f"/tmp/{chapter_title}.md",
            "new_summary": "summary",
            "new_state": "state",
        }
        if isinstance(self.result_override, dict):
            result.update(self.result_override)
        return result

    def apply_context_updates(self, *, state: str | None = None, summary_of_previous: str | None = None):
        self.apply_calls.append((state, summary_of_previous))
        return {
            "backup": {
                "state": "old state",
                "summary_of_previous": "old summary",
            },
            "applied": {
                "state": bool(state),
                "summary_of_previous": bool(summary_of_previous),
            },
        }


class TestAutomationRuntime(unittest.TestCase):
    def _load_runtime_cls(self):
        spec = importlib.util.find_spec("core.automation_runtime")
        self.assertIsNotNone(spec, "core.automation_runtime should exist")
        module = importlib.import_module("core.automation_runtime")
        runtime_cls = getattr(module, "AutomationRuntime", None)
        self.assertIsNotNone(runtime_cls, "AutomationRuntime should exist")
        return runtime_cls

    def test_runtime_executes_next_pending_job_marks_done_and_applies_legacy_context_when_enabled(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch("core.automation_store.DATA_PROJECTS_DIR", projects_dir):
                store = AutomationStore(project_name="sample")
                store.save_config(
                    {
                        "enabled": True,
                        "schedule": {"type": "daily", "time": "21:00"},
                        "context_updates": {"state": True, "summary": True},
                    }
                )
                store.save_queue(
                    [
                        {
                            "id": "job1",
                            "title": "Episode 12",
                            "instruction": "scene instruction",
                            "target_length": 5000,
                            "status": "pending",
                            "attempt_count": 0,
                        }
                    ]
                )
                fake_automator = FakeAutomator()
                runtime = runtime_cls(store=store, automator=fake_automator)

                runtime.tick(now=now)

                queue = store.load_queue()
                state = store.load_runtime()
                history = store.load_recent_history(limit=10)

        self.assertEqual(queue[0]["status"], "done")
        self.assertEqual(queue[0]["attempt_count"], 1)
        self.assertEqual(state["status"], "idle")
        self.assertEqual(state["last_run_at"], now.isoformat())
        self.assertEqual(len(history), 1)
        self.assertEqual(fake_automator.apply_calls, [("state", "summary")])
        self.assertEqual(fake_automator.run_calls[0], ("Episode 12", "scene instruction", 5000, False, "balanced"))
        self.assertEqual(history[0]["context_update"]["legacy"]["status"], "applied")
        self.assertEqual(history[0]["context_update"]["canon_candidate"]["status"], "missing")

    def test_runtime_passes_saved_plot_generation_options_to_automator(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch("core.automation_store.DATA_PROJECTS_DIR", projects_dir):
                store = AutomationStore(project_name="sample")
                store.save_config(
                    {
                        "enabled": True,
                        "schedule": {"type": "daily", "time": "21:00"},
                        "generation_options": {"include_plot": True, "plot_strength": "strict"},
                    }
                )
                store.save_queue(
                    [
                        {
                            "id": "job1",
                            "title": "Episode 12",
                            "instruction": "scene instruction",
                            "target_length": 5000,
                            "status": "pending",
                            "attempt_count": 0,
                        }
                    ]
                )
                fake_automator = FakeAutomator()
                runtime = runtime_cls(store=store, automator=fake_automator)

                runtime.tick(now=now)

        self.assertEqual(fake_automator.run_calls[0], ("Episode 12", "scene instruction", 5000, True, "strict"))

    def test_runtime_marks_job_running_before_automator_call(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch("core.automation_store.DATA_PROJECTS_DIR", projects_dir):
                store = AutomationStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "job1",
                            "title": "Episode 12",
                            "instruction": "scene instruction",
                            "target_length": 5000,
                            "status": "pending",
                            "attempt_count": 0,
                        }
                    ]
                )
                fake_automator = FakeAutomator()
                seen_statuses: list[str] = []
                fake_automator.before_return = lambda: seen_statuses.append(store.load_queue()[0]["status"])
                runtime = runtime_cls(store=store, automator=fake_automator)

                runtime.tick(now=now)

        self.assertEqual(seen_statuses, ["running"])

    def test_runtime_retries_once_then_pauses_queue_on_second_failure(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch("core.automation_store.DATA_PROJECTS_DIR", projects_dir):
                store = AutomationStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "job1",
                            "title": "Episode 12",
                            "instruction": "scene instruction",
                            "target_length": 5000,
                            "status": "pending",
                            "attempt_count": 0,
                        }
                    ]
                )
                runtime = runtime_cls(store=store, automator=FakeAutomator(should_fail=True))

                runtime.tick(now=now)

                queue = store.load_queue()
                state = store.load_runtime()

        self.assertEqual(queue[0]["status"], "failed")
        self.assertEqual(queue[0]["attempt_count"], 2)
        self.assertEqual(state["status"], "paused")
        self.assertEqual(state["last_error"], "boom")

    def test_runtime_skips_execution_when_paused(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch("core.automation_store.DATA_PROJECTS_DIR", projects_dir):
                store = AutomationStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_runtime({"status": "paused", "last_error": "boom"})
                store.save_queue(
                    [
                        {
                            "id": "job1",
                            "title": "Episode 12",
                            "instruction": "scene instruction",
                            "target_length": 5000,
                            "status": "pending",
                            "attempt_count": 0,
                        }
                    ]
                )
                fake_automator = FakeAutomator()
                runtime = runtime_cls(store=store, automator=fake_automator)

                runtime.tick(now=now)

        self.assertEqual(fake_automator.call_count, 0)

    def test_runtime_skips_legacy_context_apply_by_default(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch("core.automation_store.DATA_PROJECTS_DIR", projects_dir):
                store = AutomationStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "job1",
                            "title": "Episode 12",
                            "instruction": "scene instruction",
                            "target_length": 5000,
                            "status": "pending",
                            "attempt_count": 0,
                        }
                    ]
                )
                fake_automator = FakeAutomator()
                runtime = runtime_cls(store=store, automator=fake_automator)

                runtime.tick(now=now)

                history = store.load_recent_history(limit=10)

        self.assertEqual(fake_automator.apply_calls, [])
        self.assertEqual(history[0]["context_update"]["legacy"]["status"], "skipped")
        self.assertEqual(history[0]["context_update"]["canon_candidate"]["status"], "missing")

    def test_runtime_skips_context_apply_when_disabled(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch("core.automation_store.DATA_PROJECTS_DIR", projects_dir):
                store = AutomationStore(project_name="sample")
                store.save_config(
                    {
                        "enabled": True,
                        "schedule": {"type": "daily", "time": "21:00"},
                        "context_updates": {"state": False, "summary": False},
                    }
                )
                store.save_queue(
                    [
                        {
                            "id": "job1",
                            "title": "Episode 12",
                            "instruction": "scene instruction",
                            "target_length": 5000,
                            "status": "pending",
                            "attempt_count": 0,
                        }
                    ]
                )
                fake_automator = FakeAutomator()
                runtime = runtime_cls(store=store, automator=fake_automator)

                runtime.tick(now=now)

                history = store.load_recent_history(limit=10)

        self.assertEqual(fake_automator.apply_calls, [])
        self.assertEqual(history[0]["context_update"]["legacy"]["status"], "skipped")
        self.assertEqual(history[0]["context_update"]["canon_candidate"]["status"], "missing")

    def test_runtime_records_canon_candidate_from_cycle_result(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch("core.automation_store.DATA_PROJECTS_DIR", projects_dir):
                store = AutomationStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "job1",
                            "title": "Episode 12",
                            "instruction": "scene instruction",
                            "target_length": 5000,
                            "status": "pending",
                            "attempt_count": 0,
                        }
                    ]
                )
                fake_automator = FakeAutomator()
                fake_automator.result_override = {
                    "canon_update": {
                        "people": {"lead": {"mood": "angry"}},
                        "hooks": ["new hook"],
                    }
                }
                runtime = runtime_cls(store=store, automator=fake_automator)

                runtime.tick(now=now)

                history = store.load_recent_history(limit=10)

        self.assertEqual(history[0]["context_update"]["canon_candidate"]["status"], "recorded")
        self.assertEqual(history[0]["context_update"]["canon_candidate"]["candidate"]["people"]["lead"]["mood"], "angry")
        self.assertEqual(history[0]["context_update"]["canon_candidate"]["candidate"]["hooks"], ["new hook"])

    def test_run_automation_pass_processes_enabled_projects(self):
        module = importlib.import_module("core.automation_runtime")
        run_automation_pass = getattr(module, "run_automation_pass", None)
        self.assertIsNotNone(run_automation_pass, "run_automation_pass should exist")
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch("core.automation_store.DATA_PROJECTS_DIR", projects_dir), patch.object(
                module, "DATA_PROJECTS_DIR", projects_dir
            ):
                enabled_store = AutomationStore(project_name="enabled_project")
                enabled_store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                enabled_store.save_queue(
                    [
                        {
                            "id": "job1",
                            "title": "Episode 12",
                            "instruction": "scene instruction",
                            "target_length": 5000,
                            "status": "pending",
                            "attempt_count": 0,
                        }
                    ]
                )

                disabled_store = AutomationStore(project_name="disabled_project")
                disabled_store.save_config({"enabled": False, "schedule": {"type": "daily", "time": "21:00"}})

                automators: dict[str, FakeAutomator] = {}

                def automator_factory(project_name: str):
                    automators.setdefault(project_name, FakeAutomator())
                    return automators[project_name]

                run_automation_pass(now=now, automator_factory=automator_factory)

                enabled_queue = enabled_store.load_queue()

        self.assertEqual(enabled_queue[0]["status"], "done")
        self.assertEqual(automators["enabled_project"].call_count, 1)
        self.assertNotIn("disabled_project", automators)


if __name__ == "__main__":
    unittest.main()
