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

    def publish_job(self, *, job: dict, config: dict) -> dict:
        self.call_count += 1
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
        self.assertEqual(state["status"], "idle")
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
        self.assertEqual(state["status"], "idle")
        self.assertTrue(history)
        self.assertFalse(history[0]["success"])
        self.assertTrue(run_dirs)
        self.assertEqual(quality_report["status"], "failed")

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
                canon_snapshot_exists = canon_snapshot.exists()

        self.assertEqual(queue[0]["status"], "done")
        self.assertEqual(executor.call_count, 1)
        self.assertTrue(run_dirs)
        self.assertTrue(input_snapshot_exists)
        self.assertTrue(quality_report_exists)
        self.assertTrue(publish_result_exists)
        self.assertEqual(json.loads(canon_events[0])["episode_id"], "ep_001")
        self.assertEqual(canon_state["timeline"], ["ep_001"])
        self.assertTrue(canon_snapshot_exists)


if __name__ == "__main__":
    unittest.main()
