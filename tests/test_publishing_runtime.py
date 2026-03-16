import importlib
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from core.publishing_store import PublishingStore


class FakePublishingExecutor:
    def __init__(self, result: dict | None = None):
        self.result = result or {
            "platform_results": {
                "munpia": {"status": "done", "success": True},
            }
        }
        self.call_count = 0
        self.last_job = None

    def publish_job(self, *, job: dict, config: dict) -> dict:
        self.call_count += 1
        self.last_job = job
        return self.result


class TestPublishingRuntime(unittest.TestCase):
    def _load_runtime_cls(self):
        spec = importlib.util.find_spec("core.publishing_runtime")
        self.assertIsNotNone(spec, "core.publishing_runtime should exist")
        module = importlib.import_module("core.publishing_runtime")
        runtime_cls = getattr(module, "PublishingRuntime", None)
        self.assertIsNotNone(runtime_cls, "PublishingRuntime should exist")
        return runtime_cls

    def _write_chapter(
        self,
        projects_dir: Path,
        *,
        project_name: str = "sample",
        relative_path: str = "chapters/12화.md",
        title: str = "12화. 계약의 대가",
        body: str = "본문 " * 120,
    ) -> Path:
        chapter_path = projects_dir / project_name / relative_path
        chapter_path.parent.mkdir(parents=True, exist_ok=True)
        chapter_path.write_text(f"# {title}\n\n{body}", encoding="utf-8")
        return chapter_path

    def test_tick_skips_when_publishing_is_disabled(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": False, "schedule": {"type": "daily", "time": "21:00"}})
                executor = FakePublishingExecutor()
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

        self.assertEqual(executor.call_count, 0)

    def test_tick_runs_first_pending_job_when_schedule_is_due(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            self._write_chapter(projects_dir)
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {
                                "munpia": {"selected": True, "status": "pending"},
                            },
                        }
                    ]
                )
                executor = FakePublishingExecutor()
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

                queue = store.load_queue()
                state = store.load_runtime()
                history = store.load_recent_history(limit=10)

        self.assertEqual(executor.call_count, 1)
        self.assertEqual(queue[0]["status"], "done")
        self.assertEqual(queue[0]["attempt_count"], 1)
        self.assertEqual(queue[0]["targets"]["munpia"]["status"], "done")
        self.assertEqual(state["status"], "idle")
        self.assertEqual(state["last_run_at"], now.isoformat())
        self.assertEqual(len(history), 1)
        self.assertTrue(history[0]["success"])

    def test_tick_force_runs_pending_job_even_when_disabled_and_not_due(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 13, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            self._write_chapter(projects_dir)
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": False, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {
                                "munpia": {"selected": True, "status": "pending"},
                            },
                        }
                    ]
                )
                executor = FakePublishingExecutor()
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now, force=True)

                queue = store.load_queue()
                state = store.load_runtime()

        self.assertEqual(executor.call_count, 1)
        self.assertEqual(queue[0]["status"], "done")
        self.assertEqual(state["status"], "idle")
        self.assertEqual(state["last_run_at"], now.isoformat())

    def test_tick_marks_partial_failed_when_only_one_platform_succeeds(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)
        executor = FakePublishingExecutor(
            result={
                "platform_results": {
                    "munpia": {"status": "done", "success": True},
                    "novelpia": {
                        "status": "failed",
                        "success": False,
                        "error_type": "retryable",
                        "error_text": "editor missing",
                    },
                }
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            self._write_chapter(projects_dir)
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {
                                "munpia": {"selected": True, "status": "pending"},
                                "novelpia": {"selected": True, "status": "pending"},
                            },
                        }
                    ]
                )
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

                queue = store.load_queue()
                state = store.load_runtime()
                history = store.load_recent_history(limit=10)

        self.assertEqual(queue[0]["status"], "partial_failed")
        self.assertEqual(queue[0]["targets"]["munpia"]["status"], "done")
        self.assertEqual(queue[0]["targets"]["novelpia"]["status"], "failed")
        self.assertEqual(state["status"], "cooldown")
        self.assertFalse(history[0]["success"])
        self.assertEqual(history[0]["platform_results"]["novelpia"]["error_type"], "retryable")

    def test_tick_pauses_runtime_on_requires_user_action_error(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)
        executor = FakePublishingExecutor(
            result={
                "platform_results": {
                    "munpia": {
                        "status": "failed",
                        "success": False,
                        "error_type": "requires_user_action",
                        "error_text": "captcha required",
                    },
                }
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            self._write_chapter(projects_dir)
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {
                                "munpia": {"selected": True, "status": "pending"},
                            },
                        }
                    ]
                )
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

                queue = store.load_queue()
                state = store.load_runtime()

        self.assertEqual(queue[0]["status"], "failed")
        self.assertEqual(state["status"], "paused")
        self.assertEqual(state["last_error"], "captcha required")

    def test_tick_applies_platform_config_updates_from_executor(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)
        executor = FakePublishingExecutor(
            result={
                "platform_results": {
                    "munpia": {"status": "done", "success": True, "work_id": "created-work"},
                },
                "platform_config_updates": {
                    "munpia": {"work_id": "created-work"},
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            self._write_chapter(projects_dir)
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ):
                store = PublishingStore(project_name="sample")
                store.save_config(
                    {
                        "enabled": True,
                        "schedule": {"type": "daily", "time": "21:00"},
                        "platforms": {
                            "munpia": {"enabled": True, "work_id": ""},
                        },
                    }
                )
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {
                                "munpia": {"selected": True, "status": "pending"},
                            },
                        }
                    ]
                )
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

                config = store.load_config()

        self.assertEqual(config["platforms"]["munpia"]["work_id"], "created-work")

    def test_run_publishing_pass_only_executes_enabled_projects(self):
        module = importlib.import_module("core.publishing_runtime")
        run_publishing_pass = getattr(module, "run_publishing_pass", None)
        self.assertIsNotNone(run_publishing_pass, "run_publishing_pass should exist")
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch.object(
                module, "DATA_PROJECTS_DIR", projects_dir
            ), patch("core.chapter_source.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.canon_store.DATA_PROJECTS_DIR", projects_dir):
                self._write_chapter(projects_dir, project_name="enabled_project")
                enabled_store = PublishingStore(project_name="enabled_project")
                enabled_store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                enabled_store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {
                                "munpia": {"selected": True, "status": "pending"},
                            },
                        }
                    ]
                )

                disabled_store = PublishingStore(project_name="disabled_project")
                disabled_store.save_config({"enabled": False, "schedule": {"type": "daily", "time": "21:00"}})

                executors: dict[str, FakePublishingExecutor] = {}

                def executor_factory(project_name: str):
                    executors.setdefault(project_name, FakePublishingExecutor())
                    return executors[project_name]

                run_publishing_pass(now=now, executor_factory=executor_factory)

                enabled_queue = enabled_store.load_queue()

        self.assertEqual(enabled_queue[0]["status"], "done")
        self.assertEqual(executors["enabled_project"].call_count, 1)
        self.assertNotIn("disabled_project", executors)

    def test_tick_skips_when_policy_returns_skip(self):
        module = importlib.import_module("core.publishing_runtime")
        runtime_cls = getattr(module, "PublishingRuntime")
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.canon_store.DATA_PROJECTS_DIR", projects_dir), patch.object(
                module,
                "evaluate_release_policy",
                return_value={
                    "action": "skip",
                    "reason": "cooldown",
                    "allowed_platforms": [],
                    "blocked_platforms": {},
                    "burst_slot": False,
                    "next_runtime_status": "cooldown",
                },
            ) as evaluate_release_policy, patch.object(module, "select_runnable_job") as select_runnable_job:
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                executor = FakePublishingExecutor()
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)
                state = store.load_runtime()

        evaluate_release_policy.assert_called_once()
        select_runnable_job.assert_not_called()
        self.assertEqual(executor.call_count, 0)
        self.assertEqual(state["status"], "cooldown")

    def test_tick_passes_allowed_platforms_into_queue_selector(self):
        module = importlib.import_module("core.publishing_runtime")
        runtime_cls = getattr(module, "PublishingRuntime")
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.canon_store.DATA_PROJECTS_DIR", projects_dir), patch.object(
                module,
                "evaluate_release_policy",
                return_value={
                    "action": "run_now",
                    "reason": "",
                    "allowed_platforms": ["novelpia"],
                    "blocked_platforms": {"munpia": "daily_limit_reached"},
                    "burst_slot": False,
                    "next_runtime_status": "idle",
                },
            ), patch.object(
                module,
                "select_runnable_job",
                return_value={"action": "skip", "reason": "no_job", "job": None},
            ) as select_runnable_job:
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {
                                "munpia": {"selected": True, "status": "pending"},
                                "novelpia": {"selected": True, "status": "pending"},
                            },
                        }
                    ]
                )
                executor = FakePublishingExecutor()
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

        select_runnable_job.assert_called_once()
        _, kwargs = select_runnable_job.call_args
        self.assertEqual(kwargs["allowed_platforms"], {"novelpia"})
        self.assertEqual(executor.call_count, 0)

    def test_tick_filters_executor_job_targets_to_allowed_platforms(self):
        module = importlib.import_module("core.publishing_runtime")
        runtime_cls = getattr(module, "PublishingRuntime")
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)
        executor = FakePublishingExecutor(
            result={
                "platform_results": {
                    "novelpia": {"status": "done", "success": True},
                }
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            self._write_chapter(projects_dir)
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ), patch.object(
                module,
                "evaluate_release_policy",
                return_value={
                    "action": "run_now",
                    "reason": "",
                    "allowed_platforms": ["novelpia"],
                    "blocked_platforms": {"munpia": "daily_limit_reached"},
                    "burst_slot": False,
                    "next_runtime_status": "idle",
                },
            ), patch.object(
                module,
                "summarize_publish_attempt",
                return_value={
                    "job_status": "partial_failed",
                    "runtime_status": "idle",
                    "incident_type": "",
                    "needs_user_action": False,
                    "last_error": "",
                },
            ), patch.object(module, "finalize_publish_canon", return_value={"status": "skipped"}):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {
                                "munpia": {"selected": True, "status": "pending"},
                                "novelpia": {"selected": True, "status": "pending"},
                            },
                        }
                    ]
                )
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

        self.assertEqual(executor.call_count, 1)
        self.assertEqual(set(executor.last_job["targets"].keys()), {"munpia", "novelpia"})
        self.assertFalse(executor.last_job["targets"]["munpia"]["selected"])
        self.assertTrue(executor.last_job["targets"]["novelpia"]["selected"])

    def test_tick_records_hard_fail_quality_without_calling_executor(self):
        module = importlib.import_module("core.publishing_runtime")
        runtime_cls = getattr(module, "PublishingRuntime")
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            self._write_chapter(projects_dir)
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ), patch.object(
                module,
                "select_runnable_job",
                return_value={
                    "action": "run_now",
                    "reason": "",
                    "job": {
                        "id": "pub1",
                        "source_path": "chapters/12화.md",
                        "chapter_title": "Episode 12",
                        "status": "pending",
                        "attempt_count": 0,
                        "targets": {"munpia": {"selected": True, "status": "pending"}},
                    },
                },
            ), patch.object(
                module,
                "evaluate_quality_gate",
                return_value={
                    "status": "hard_fail",
                    "attempted_repair": False,
                    "final_source": {
                        "title": "12화. 계약의 대가",
                        "content": "# 12화. 계약의 대가\n\n문제가 있는 본문",
                    },
                    "gate_reports": {
                        "initial": {
                            "rules": {"status": "hard_fail", "errors": ["bad title"]},
                            "structure": {"status": "passed", "errors": []},
                        }
                    },
                    "errors": ["bad title"],
                    "repair_summary": {"status": "skipped", "reason": "initial hard fail"},
                },
            ):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {"munpia": {"selected": True, "status": "pending"}},
                        }
                    ]
                )
                executor = FakePublishingExecutor()
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)
                queue = store.load_queue()

        self.assertEqual(executor.call_count, 0)
        self.assertEqual(queue[0]["status"], "failed")

    def test_tick_sets_runtime_blocked_for_orchestrator_hard_fail(self):
        module = importlib.import_module("core.publishing_runtime")
        runtime_cls = getattr(module, "PublishingRuntime")
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            self._write_chapter(projects_dir)
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ), patch.object(
                module,
                "evaluate_release_policy",
                return_value={
                    "action": "run_now",
                    "reason": "",
                    "allowed_platforms": ["munpia"],
                    "blocked_platforms": {},
                    "burst_slot": False,
                    "next_runtime_status": "idle",
                },
            ), patch.object(
                module,
                "select_runnable_job",
                return_value={
                    "action": "run_now",
                    "reason": "",
                    "job": {
                        "id": "pub1",
                        "source_path": "chapters/12화.md",
                        "chapter_title": "Episode 12",
                        "status": "pending",
                        "attempt_count": 0,
                        "targets": {"munpia": {"selected": True, "status": "pending"}},
                    },
                },
            ), patch.object(
                module,
                "evaluate_quality_gate",
                return_value={
                    "status": "hard_fail",
                    "attempted_repair": False,
                    "final_source": {
                        "title": "12화. 계약의 대가",
                        "content": "# 12화. 계약의 대가\n\n문제가 있는 본문",
                    },
                    "gate_reports": {
                        "initial": {
                            "rules": {"status": "hard_fail", "errors": ["bad title"]},
                            "structure": {"status": "passed", "errors": []},
                        }
                    },
                    "errors": ["bad title"],
                    "repair_summary": {"status": "skipped", "reason": "initial hard fail"},
                },
            ):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {"munpia": {"selected": True, "status": "pending"}},
                        }
                    ]
                )
                executor = FakePublishingExecutor()
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)
                queue = store.load_queue()
                state = store.load_runtime()
                history = store.load_recent_history(limit=10)

        self.assertEqual(executor.call_count, 0)
        self.assertEqual(queue[0]["status"], "failed")
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(history[0]["publish_quality"]["status"], "hard_fail")

    def test_tick_passes_episode_plan_into_quality_gate_when_source_provides_it(self):
        module = importlib.import_module("core.publishing_runtime")
        runtime_cls = getattr(module, "PublishingRuntime")
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            self._write_chapter(projects_dir)
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.canon_store.DATA_PROJECTS_DIR", projects_dir), patch.object(
                module,
                "load_chapter_source",
                return_value={
                    "path": str(projects_dir / "sample" / "chapters" / "12화.md"),
                    "title": "12화. 계약의 대가",
                    "content": "# 12화. 계약의 대가\n\n" + ("정상 본문입니다.\n" * 60),
                    "episode_id": "ep_012",
                    "episode_plan": {"episode_objective": "계약의 대가를 수습한다"},
                },
            ), patch.object(
                module,
                "evaluate_quality_gate",
                return_value={
                    "status": "hard_fail",
                    "attempted_repair": False,
                    "final_source": {
                        "title": "12화. 계약의 대가",
                        "content": "# 12화. 계약의 대가\n\n문제가 있는 본문",
                    },
                    "gate_reports": {
                        "final": {
                            "critic": {
                                "status": "blocked",
                                "summary": "objective drift",
                                "issues": ["episode objective missing"],
                            }
                        }
                    },
                    "errors": ["episode objective missing"],
                    "repair_summary": {"status": "skipped", "reason": "objective drift"},
                },
            ) as evaluate_quality_gate:
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {"munpia": {"selected": True, "status": "pending"}},
                        }
                    ]
                )
                executor = FakePublishingExecutor()
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

        self.assertEqual(evaluate_quality_gate.call_args.kwargs["episode_plan"]["episode_objective"], "계약의 대가를 수습한다")

    def test_tick_uses_orchestrator_final_source_for_executor_payload(self):
        module = importlib.import_module("core.publishing_runtime")
        runtime_cls = getattr(module, "PublishingRuntime")
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)
        executor = FakePublishingExecutor()
        repaired_content = "# 12화. 계약의 대가\n\n수정된 본문입니다.\n" + ("장면 정리.\n" * 40)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            self._write_chapter(projects_dir)
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ), patch.object(
                module,
                "evaluate_release_policy",
                return_value={
                    "action": "run_now",
                    "reason": "",
                    "allowed_platforms": ["munpia"],
                    "blocked_platforms": {},
                    "burst_slot": False,
                    "next_runtime_status": "idle",
                },
            ), patch.object(
                module,
                "select_runnable_job",
                return_value={
                    "action": "run_now",
                    "reason": "",
                    "job": {
                        "id": "pub1",
                        "source_path": "chapters/12화.md",
                        "chapter_title": "Episode 12",
                        "status": "pending",
                        "attempt_count": 0,
                        "targets": {"munpia": {"selected": True, "status": "pending"}},
                    },
                },
            ), patch.object(
                module,
                "evaluate_quality_gate",
                return_value={
                    "status": "publishable",
                    "attempted_repair": True,
                    "final_source": {
                        "title": "12화. 계약의 대가",
                        "content": repaired_content,
                    },
                    "gate_reports": {
                        "initial": {
                            "rules": {"status": "publishable", "errors": []},
                            "structure": {"status": "retry_possible", "errors": ["auxiliary marker detected"]},
                        },
                        "final": {
                            "rules": {"status": "publishable", "errors": []},
                            "structure": {"status": "passed", "errors": []},
                        },
                    },
                    "errors": [],
                    "repair_summary": {"status": "applied", "reason": ""},
                },
            ), patch.object(
                module,
                "summarize_publish_attempt",
                return_value={
                    "job_status": "done",
                    "runtime_status": "idle",
                    "incident_type": "",
                    "needs_user_action": False,
                    "last_error": "",
                },
            ), patch.object(module, "finalize_publish_canon", return_value={"status": "skipped"}):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {"munpia": {"selected": True, "status": "pending"}},
                        }
                    ]
                )
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

        self.assertEqual(executor.call_count, 1)
        self.assertEqual(executor.last_job["source_override"]["content"], repaired_content)

    def test_tick_writes_orchestrator_report_to_quality_snapshot(self):
        module = importlib.import_module("core.publishing_runtime")
        runtime_cls = getattr(module, "PublishingRuntime")
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)
        quality_result = {
            "status": "publishable",
            "attempted_repair": True,
            "final_source": {
                "title": "12화. 계약의 대가",
                "content": "# 12화. 계약의 대가\n\n정리된 본문",
            },
            "gate_reports": {
                "initial": {
                    "rules": {"status": "publishable", "errors": []},
                    "structure": {"status": "retry_possible", "errors": ["auxiliary marker detected"]},
                },
                "final": {
                    "rules": {"status": "publishable", "errors": []},
                    "structure": {"status": "passed", "errors": []},
                },
            },
            "errors": [],
            "repair_summary": {"status": "applied", "reason": ""},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            self._write_chapter(projects_dir)
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ), patch.object(
                module,
                "evaluate_release_policy",
                return_value={
                    "action": "run_now",
                    "reason": "",
                    "allowed_platforms": ["munpia"],
                    "blocked_platforms": {},
                    "burst_slot": False,
                    "next_runtime_status": "idle",
                },
            ), patch.object(
                module,
                "select_runnable_job",
                return_value={
                    "action": "run_now",
                    "reason": "",
                    "job": {
                        "id": "pub1",
                        "source_path": "chapters/12화.md",
                        "chapter_title": "Episode 12",
                        "status": "pending",
                        "attempt_count": 0,
                        "targets": {"munpia": {"selected": True, "status": "pending"}},
                    },
                },
            ), patch.object(module, "evaluate_quality_gate", return_value=quality_result), patch.object(
                module,
                "summarize_publish_attempt",
                return_value={
                    "job_status": "done",
                    "runtime_status": "idle",
                    "incident_type": "",
                    "needs_user_action": False,
                    "last_error": "",
                },
            ), patch.object(module, "finalize_publish_canon", return_value={"status": "skipped"}):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {"munpia": {"selected": True, "status": "pending"}},
                        }
                    ]
                )
                executor = FakePublishingExecutor()
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)
                run_dirs = list((projects_dir / "sample" / "runs").glob("*"))
                quality_report = json.loads((run_dirs[0] / "quality_report.json").read_text(encoding="utf-8"))

        self.assertEqual(quality_report, quality_result)

    def test_tick_uses_incident_summary_to_set_runtime_and_job_status(self):
        module = importlib.import_module("core.publishing_runtime")
        runtime_cls = getattr(module, "PublishingRuntime")
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            self._write_chapter(projects_dir)
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ), patch.object(
                module,
                "select_runnable_job",
                return_value={
                    "action": "run_now",
                    "reason": "",
                    "job": {
                        "id": "pub1",
                        "source_path": "chapters/12화.md",
                        "chapter_title": "Episode 12",
                        "status": "pending",
                        "attempt_count": 0,
                        "targets": {"munpia": {"selected": True, "status": "pending"}},
                    },
                },
            ), patch.object(
                module,
                "evaluate_quality_gate",
                return_value={
                    "status": "publishable",
                    "attempted_repair": False,
                    "final_source": {
                        "title": "12화. 계약의 대가",
                        "content": "# 12화. 계약의 대가\n\n유효한 본문",
                    },
                    "gate_reports": {
                        "initial": {
                            "rules": {"status": "publishable", "errors": []},
                            "structure": {"status": "passed", "errors": []},
                        }
                    },
                    "errors": [],
                    "repair_summary": {"status": "not_needed", "reason": ""},
                },
            ), patch.object(
                module,
                "summarize_publish_attempt",
                return_value={
                    "job_status": "partial_failed",
                    "runtime_status": "cooldown",
                    "incident_type": "platform_incident",
                    "needs_user_action": False,
                    "last_error": "timeout",
                },
            ):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {"munpia": {"selected": True, "status": "pending"}},
                        }
                    ]
                )
                executor = FakePublishingExecutor()
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)
                queue = store.load_queue()
                state = store.load_runtime()

        self.assertEqual(queue[0]["status"], "partial_failed")
        self.assertEqual(state["status"], "cooldown")
        self.assertEqual(state["last_error"], "timeout")

    def test_tick_persists_blocked_runtime_state_from_incident_summary(self):
        module = importlib.import_module("core.publishing_runtime")
        runtime_cls = getattr(module, "PublishingRuntime")
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            self._write_chapter(projects_dir)
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ), patch.object(
                module,
                "select_runnable_job",
                return_value={
                    "action": "run_now",
                    "reason": "",
                    "job": {
                        "id": "pub1",
                        "source_path": "chapters/12화.md",
                        "chapter_title": "Episode 12",
                        "status": "pending",
                        "attempt_count": 0,
                        "targets": {"munpia": {"selected": True, "status": "pending"}},
                    },
                },
            ), patch.object(
                module,
                "evaluate_quality_gate",
                return_value={
                    "status": "publishable",
                    "attempted_repair": False,
                    "final_source": {
                        "title": "12화. 계약의 대가",
                        "content": "# 12화. 계약의 대가\n\n유효한 본문",
                    },
                    "gate_reports": {
                        "initial": {
                            "rules": {"status": "publishable", "errors": []},
                            "structure": {"status": "passed", "errors": []},
                        }
                    },
                    "errors": [],
                    "repair_summary": {"status": "not_needed", "reason": ""},
                },
            ), patch.object(
                module,
                "summarize_publish_attempt",
                return_value={
                    "job_status": "failed",
                    "runtime_status": "blocked",
                    "incident_type": "data_integrity_incident",
                    "needs_user_action": False,
                    "last_error": "no selected targets",
                },
            ):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {"munpia": {"selected": True, "status": "pending"}},
                        }
                    ]
                )
                executor = FakePublishingExecutor()
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)
                queue = store.load_queue()
                state = store.load_runtime()

        self.assertEqual(queue[0]["status"], "failed")
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["last_error"], "no selected targets")

    def test_tick_delegates_canon_finalize_after_successful_publish(self):
        module = importlib.import_module("core.publishing_runtime")
        runtime_cls = getattr(module, "PublishingRuntime")
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            self._write_chapter(projects_dir)
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ), patch.object(
                module,
                "select_runnable_job",
                return_value={
                    "action": "run_now",
                    "reason": "",
                    "job": {
                        "id": "pub1",
                        "episode_id": "ep_012",
                        "source_path": "chapters/12화.md",
                        "chapter_title": "Episode 12",
                        "status": "pending",
                        "attempt_count": 0,
                        "targets": {"munpia": {"selected": True, "status": "pending"}},
                    },
                },
            ), patch.object(
                module,
                "evaluate_quality_gate",
                return_value={
                    "status": "publishable",
                    "attempted_repair": False,
                    "final_source": {
                        "title": "12화. 계약의 대가",
                        "content": "# 12화. 계약의 대가\n\n유효한 본문",
                    },
                    "gate_reports": {
                        "initial": {
                            "rules": {"status": "publishable", "errors": []},
                            "structure": {"status": "passed", "errors": []},
                        }
                    },
                    "errors": [],
                    "repair_summary": {"status": "not_needed", "reason": ""},
                },
            ), patch.object(
                module,
                "summarize_publish_attempt",
                return_value={
                    "job_status": "done",
                    "runtime_status": "idle",
                    "incident_type": "",
                    "needs_user_action": False,
                    "last_error": "",
                },
            ), patch.object(
                module,
                "finalize_publish_canon",
                return_value={"status": "applied", "source": "result", "candidate": {"timeline": ["ep_012"]}, "error": ""},
            ) as finalize_publish_canon:
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "episode_id": "ep_012",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {"munpia": {"selected": True, "status": "pending"}},
                        }
                    ]
                )
                executor = FakePublishingExecutor()
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

        finalize_publish_canon.assert_called_once()

    def test_tick_blocks_publication_when_origin_quality_fails(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "프롤로그.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            chapter_path.write_text("# 프롤로그\n\n짧다", encoding="utf-8")

            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "episode_id": "ep_000",
                            "chapter_title": "프롤로그",
                            "source_path": "chapters/프롤로그.md",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {
                                "munpia": {"selected": True, "status": "pending"},
                            },
                        }
                    ]
                )
                executor = FakePublishingExecutor()
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

                queue = store.load_queue()
                state = store.load_runtime()
                history = store.load_recent_history(limit=10)
                run_dirs = list((projects_dir / "sample" / "runs").glob("*"))
                quality_report = json.loads((run_dirs[0] / "quality_report.json").read_text(encoding="utf-8"))

        self.assertEqual(executor.call_count, 0)
        self.assertEqual(queue[0]["status"], "failed")
        self.assertEqual(state["status"], "blocked")
        self.assertTrue(history)
        self.assertFalse(history[0]["success"])
        self.assertTrue(run_dirs)
        self.assertEqual(quality_report["status"], "hard_fail")

    def test_tick_preserves_critic_report_in_quality_snapshot(self):
        module = importlib.import_module("core.publishing_runtime")
        runtime_cls = getattr(module, "PublishingRuntime")
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)
        quality_result = {
            "status": "hard_fail",
            "attempted_repair": False,
            "final_source": {
                "title": "12화. 계약의 대가",
                "content": "# 12화. 계약의 대가\n\n문제가 있는 본문",
            },
            "gate_reports": {
                "initial": {
                    "rules": {"status": "publishable", "errors": []},
                    "structure": {"status": "passed", "errors": []},
                },
                "final": {
                    "rules": {"status": "publishable", "errors": []},
                    "structure": {"status": "passed", "errors": []},
                    "critic": {
                        "status": "blocked",
                        "summary": "objective drift",
                        "issues": ["episode objective missing"],
                    },
                },
            },
            "errors": ["episode objective missing", "objective drift"],
            "repair_summary": {"status": "skipped", "reason": "objective drift"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            self._write_chapter(projects_dir)
            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ), patch.object(
                module,
                "evaluate_quality_gate",
                return_value=quality_result,
            ):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "source_path": "chapters/12화.md",
                            "chapter_title": "Episode 12",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {"munpia": {"selected": True, "status": "pending"}},
                        }
                    ]
                )
                executor = FakePublishingExecutor()
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)
                run_dirs = list((projects_dir / "sample" / "runs").glob("*"))
                quality_report = json.loads((run_dirs[0] / "quality_report.json").read_text(encoding="utf-8"))

        self.assertEqual(executor.call_count, 0)
        self.assertEqual(quality_report["gate_reports"]["final"]["critic"]["status"], "blocked")
        self.assertIn("episode objective missing", quality_report["errors"])

    def test_tick_writes_run_snapshots_and_updates_canon_only_on_success(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "1화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            chapter_path.write_text("# 1화. 시작\n\n" + ("첫 문단입니다.\n둘째 문단입니다.\n" * 30), encoding="utf-8")

            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ), patch(
                "core.publishing_canon.extract_canon_update",
                return_value={
                    "people": {"lead": {"mood": "curious"}},
                    "resources": {},
                    "hooks": [],
                    "timeline": [],
                },
            ):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub1",
                            "episode_id": "ep_001",
                            "chapter_title": "1화. 시작",
                            "source_path": "chapters/1화.md",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {
                                "munpia": {"selected": True, "status": "pending"},
                            },
                        }
                    ]
                )
                executor = FakePublishingExecutor()
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

                queue = store.load_queue()
                run_dirs = list((projects_dir / "sample" / "runs").glob("*"))
                canon_events = (projects_dir / "sample" / "canon" / "events.jsonl").read_text(encoding="utf-8").splitlines()
                canon_state = json.loads((projects_dir / "sample" / "canon" / "current_state.json").read_text(encoding="utf-8"))
                canon_snapshot = projects_dir / "sample" / "canon" / "snapshots" / "ep_001.json"
                input_snapshot_exists = (run_dirs[0] / "input_snapshot.json").exists()
                quality_report_exists = (run_dirs[0] / "quality_report.json").exists()
                publish_result_exists = (run_dirs[0] / "publish_result.json").exists()
                canon_update_snapshot_exists = (run_dirs[0] / "canon_update.json").exists()
                canon_snapshot_exists = canon_snapshot.exists()

        self.assertEqual(queue[0]["status"], "done")
        self.assertEqual(executor.call_count, 1)
        self.assertTrue(run_dirs)
        self.assertTrue(input_snapshot_exists)
        self.assertTrue(quality_report_exists)
        self.assertTrue(publish_result_exists)
        self.assertTrue(canon_update_snapshot_exists)
        self.assertEqual(json.loads(canon_events[0])["episode_id"], "ep_001")
        self.assertEqual(json.loads(canon_events[0])["canon_update_status"], "applied")
        self.assertEqual(canon_state["timeline"], ["ep_001"])
        self.assertEqual(canon_state["people"]["lead"]["mood"], "curious")
        self.assertTrue(canon_snapshot_exists)

    def test_tick_applies_canon_update_payload_when_publish_succeeds(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)
        executor = FakePublishingExecutor(
            result={
                "platform_results": {
                    "munpia": {"status": "done", "success": True},
                },
                "canon_update": {
                    "people": {"lead": {"mood": "angry"}},
                    "resources": {"cash": 2000},
                    "hooks": ["new hook"],
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "2화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            body = "\n".join(f"장면 {index}: 다른 문장입니다." for index in range(80))
            chapter_path.write_text("# 2화. 확장\n\n" + body, encoding="utf-8")

            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub2",
                            "episode_id": "ep_002",
                            "chapter_title": "2화. 확장",
                            "source_path": "chapters/2화.md",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {
                                "munpia": {"selected": True, "status": "pending"},
                            },
                        }
                    ]
                )
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

                canon_state = json.loads((projects_dir / "sample" / "canon" / "current_state.json").read_text(encoding="utf-8"))

        self.assertEqual(canon_state["people"]["lead"]["mood"], "angry")
        self.assertEqual(canon_state["resources"]["cash"], 2000)
        self.assertEqual(canon_state["hooks"], ["new hook"])
        self.assertEqual(canon_state["timeline"], ["ep_002"])

    def test_tick_uses_extractor_fallback_when_publish_result_has_no_canon_update(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)
        executor = FakePublishingExecutor(
            result={
                "platform_results": {
                    "munpia": {"status": "done", "success": True},
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "3화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            body = "\n".join(f"장면 {index}: 다른 문장입니다." for index in range(80))
            chapter_path.write_text("# 3화. 낙차\n\n" + body, encoding="utf-8")

            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ), patch(
                "core.publishing_canon.extract_canon_update",
                return_value={
                    "people": {"lead": {"mood": "shaken"}},
                    "hooks": ["fresh hook"],
                    "resources": {},
                    "timeline": [],
                },
            ):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub3",
                            "episode_id": "ep_003",
                            "chapter_title": "3화. 낙차",
                            "source_path": "chapters/3화.md",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {
                                "munpia": {"selected": True, "status": "pending"},
                            },
                        }
                    ]
                )
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

                canon_state = json.loads((projects_dir / "sample" / "canon" / "current_state.json").read_text(encoding="utf-8"))

        self.assertEqual(canon_state["people"]["lead"]["mood"], "shaken")
        self.assertEqual(canon_state["hooks"], ["fresh hook"])
        self.assertEqual(canon_state["timeline"], ["ep_003"])

    def test_tick_prefers_artifact_canon_update_before_extractor_fallback(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)
        executor = FakePublishingExecutor(
            result={
                "platform_results": {
                    "munpia": {"status": "done", "success": True},
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "6화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            body = "\n".join(f"장면 {index}: 다른 문장입니다." for index in range(80))
            chapter_path.write_text("# 6화. 저장 후보\n\n" + body, encoding="utf-8")

            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ), patch(
                "core.episode_artifact_store.DATA_PROJECTS_DIR", projects_dir
            ), patch(
                "core.publishing_canon.extract_canon_update",
                side_effect=AssertionError("extractor should not be called"),
            ):
                from core.episode_artifact_store import EpisodeArtifactStore

                store = PublishingStore(project_name="sample")
                artifact_store = EpisodeArtifactStore(project_name="sample")
                artifact_store.create_draft(
                    title="6화. 저장 후보",
                    content="# 6화. 저장 후보\n\n" + body,
                    episode_id="ep_006",
                )
                artifact_store.promote_to_publishable("ep_006")
                artifact_store.save_canon_update("ep_006", {"people": {"lead": {"mood": "stored"}}})
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub6",
                            "episode_id": "ep_006",
                            "chapter_title": "6화. 저장 후보",
                            "source_path": "chapters/6화.md",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {
                                "munpia": {"selected": True, "status": "pending"},
                            },
                        }
                    ]
                )
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

                canon_state = json.loads((projects_dir / "sample" / "canon" / "current_state.json").read_text(encoding="utf-8"))
                history = store.load_recent_history(limit=10)

        self.assertEqual(canon_state["people"]["lead"]["mood"], "stored")
        self.assertEqual(history[0]["canon_update"]["source"], "artifact")

    def test_tick_skips_canon_update_when_extractor_fails(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)
        executor = FakePublishingExecutor(
            result={
                "platform_results": {
                    "munpia": {"status": "done", "success": True},
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "4화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            body = "\n".join(f"장면 {index}: 다른 문장입니다." for index in range(80))
            chapter_path.write_text("# 4화. 누락\n\n" + body, encoding="utf-8")

            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ), patch(
                "core.publishing_canon.extract_canon_update",
                side_effect=RuntimeError("canon extract failed"),
            ):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub4",
                            "episode_id": "ep_004",
                            "chapter_title": "4화. 누락",
                            "source_path": "chapters/4화.md",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {
                                "munpia": {"selected": True, "status": "pending"},
                            },
                        }
                    ]
                )
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

                history = store.load_recent_history(limit=10)
                canon_state_path = projects_dir / "sample" / "canon" / "current_state.json"

        self.assertFalse(canon_state_path.exists())
        self.assertEqual(history[0]["canon_update"]["status"], "failed")
        self.assertEqual(history[0]["canon_update"]["source"], "extractor")

    def test_tick_writes_canon_update_snapshot_and_history_record(self):
        runtime_cls = self._load_runtime_cls()
        now = datetime(2026, 3, 12, 21, 0, tzinfo=timezone.utc)
        executor = FakePublishingExecutor(
            result={
                "platform_results": {
                    "munpia": {"status": "done", "success": True},
                },
                "canon_update": {
                    "people": {"lead": {"mood": "resolved"}},
                    "resources": {},
                    "hooks": [],
                    "timeline": [],
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir) / "projects"
            chapter_path = projects_dir / "sample" / "chapters" / "5화.md"
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            body = "\n".join(f"장면 {index}: 다른 문장입니다." for index in range(80))
            chapter_path.write_text("# 5화. 기록\n\n" + body, encoding="utf-8")

            with patch("core.publishing_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.chapter_source.DATA_PROJECTS_DIR", projects_dir
            ), patch("core.run_snapshot_store.DATA_PROJECTS_DIR", projects_dir), patch(
                "core.canon_store.DATA_PROJECTS_DIR", projects_dir
            ):
                store = PublishingStore(project_name="sample")
                store.save_config({"enabled": True, "schedule": {"type": "daily", "time": "21:00"}})
                store.save_queue(
                    [
                        {
                            "id": "pub5",
                            "episode_id": "ep_005",
                            "chapter_title": "5화. 기록",
                            "source_path": "chapters/5화.md",
                            "status": "pending",
                            "attempt_count": 0,
                            "targets": {
                                "munpia": {"selected": True, "status": "pending"},
                            },
                        }
                    ]
                )
                runtime = runtime_cls(store=store, executor=executor)

                runtime.tick(now=now)

                history = store.load_recent_history(limit=10)
                run_dirs = list((projects_dir / "sample" / "runs").glob("*"))
                canon_snapshot_payload = json.loads((run_dirs[0] / "canon_update.json").read_text(encoding="utf-8"))
                canon_events = (projects_dir / "sample" / "canon" / "events.jsonl").read_text(encoding="utf-8").splitlines()

        self.assertEqual(history[0]["canon_update"]["status"], "applied")
        self.assertEqual(history[0]["canon_update"]["source"], "result")
        self.assertEqual(canon_snapshot_payload["status"], "applied")
        self.assertEqual(json.loads(canon_events[0])["canon_update_status"], "applied")


if __name__ == "__main__":
    unittest.main()
