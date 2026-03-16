# Publish Control Plane v1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal publish control plane that standardizes publishing policy, low-cost quality gating, incident classification, and Canon finalization without changing the external upload behavior.

**Architecture:** Keep `PublishingRuntime` as a thin coordinator and move decision-making into four focused modules: policy selection, quality evaluation, incident summarization, and Canon finalize logic. Reuse existing stores, executor, and chapter source loading, but make runtime state transitions and publishability decisions explicit in code and tests.

**Tech Stack:** Python, unittest, existing `PublishingStore`, `PublishingRuntime`, `PublishingExecutor`, `CanonStore`, `RunSnapshotStore`, `origin_quality`, `automation_scheduler`

---

## File Structure

### New files

- `core/publishing_policy.py`
  - Selects whether a publishing tick should run and which job should run now.
- `core/publishing_quality.py`
  - Wraps low-cost source validation and maps raw validation output to control-plane statuses.
- `core/publishing_incidents.py`
  - Converts platform publish results into job status, runtime status, incident type, and last error.
- `core/publishing_canon.py`
  - Resolves Canon candidates and applies Canon updates only after successful publication.
- `tests/test_publishing_policy.py`
  - Unit tests for runnable-job selection and skip reasons.
- `tests/test_publishing_quality.py`
  - Unit tests for low-cost quality gate result normalization.
- `tests/test_publishing_incidents.py`
  - Unit tests for publish-result summarization and runtime transitions.
- `tests/test_publishing_canon.py`
  - Unit tests for candidate priority and Canon finalize rules.

### Modified files

- `core/publishing_runtime.py`
  - Reduced to orchestration and persistence only.
- `tests/test_publishing_runtime.py`
  - Rebalanced toward coordinator behavior instead of detailed branching logic.

### Existing files to reference

- `core/publishing_store.py`
- `core/publishing_executor.py`
- `core/chapter_source.py`
- `core/origin_quality.py`
- `core/canon_extractor.py`
- `core/canon_candidate.py`
- `core/automation_scheduler.py`
- `tests/test_publishing_executor.py`

## Chunk 1: Add publish policy and quality boundaries

### Task 1: Add failing tests for publish policy selection

**Files:**
- Create: `tests/test_publishing_policy.py`
- Create: `core/publishing_policy.py`

- [ ] **Step 1: Write the failing policy tests**

```python
import unittest
from datetime import datetime

from core.publishing_policy import select_runnable_job


class TestPublishingPolicy(unittest.TestCase):
    def test_select_runnable_job_skips_when_disabled(self):
        decision = select_runnable_job(
            config={"enabled": False, "schedule": {"type": "daily", "time": "21:00", "days": [], "hours": 24}},
            runtime={"status": "idle", "last_run_at": None},
            queue=[{"id": "job-1", "status": "pending"}],
            now=datetime(2026, 3, 16, 21, 0),
        )
        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "disabled")

    def test_select_runnable_job_skips_when_runtime_is_paused(self):
        decision = select_runnable_job(
            config={"enabled": True, "schedule": {"type": "daily", "time": "21:00", "days": [], "hours": 24}},
            runtime={"status": "paused", "last_run_at": None},
            queue=[{"id": "job-1", "status": "pending"}],
            now=datetime(2026, 3, 16, 21, 0),
        )
        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "paused")

    def test_select_runnable_job_returns_first_pending_or_partial_failed_job_when_due(self):
        decision = select_runnable_job(
            config={"enabled": True, "schedule": {"type": "daily", "time": "21:00", "days": [], "hours": 24}},
            runtime={"status": "idle", "last_run_at": None},
            queue=[
                {"id": "job-1", "status": "done"},
                {"id": "job-2", "status": "partial_failed"},
                {"id": "job-3", "status": "pending"},
            ],
            now=datetime(2026, 3, 16, 21, 0),
        )
        self.assertEqual(decision["action"], "run_now")
        self.assertEqual(decision["reason"], "")
        self.assertEqual(decision["job"]["id"], "job-2")
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_policy -v`

Expected: FAIL because `core/publishing_policy.py` does not exist yet.

- [ ] **Step 3: Write the minimal policy implementation**

Create `core/publishing_policy.py` with:

- `select_runnable_job(*, config: dict, runtime: dict, queue: list[dict], now: datetime) -> dict`
- skip reasons:
  - `disabled`
  - `paused`
  - `running`
  - `not_due`
  - `no_job`
- `run_now` path returning the first `pending` or `partial_failed` job
- reuse `is_schedule_due(...)` from `core.automation_scheduler`

- [ ] **Step 4: Re-run the focused tests to verify they pass**

Run: `python3 -m unittest tests.test_publishing_policy -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/publishing_policy.py tests/test_publishing_policy.py
git commit -m "feat: add publishing policy selection"
```

### Task 2: Add failing tests for low-cost publishing quality evaluation

**Files:**
- Create: `tests/test_publishing_quality.py`
- Create: `core/publishing_quality.py`

- [ ] **Step 1: Write the failing quality tests**

```python
import unittest

from core.publishing_quality import evaluate_publish_source


class TestPublishingQuality(unittest.TestCase):
    def test_evaluate_publish_source_returns_hard_fail_for_invalid_title_and_short_body(self):
        report = evaluate_publish_source({"title": "프롤로그", "content": "짧다"})
        self.assertEqual(report["status"], "hard_fail")
        self.assertGreaterEqual(len(report["errors"]), 1)

    def test_evaluate_publish_source_returns_hard_fail_for_blocked_markers(self):
        report = evaluate_publish_source({"title": "1화", "content": "검수리포트 초안"})
        self.assertEqual(report["status"], "hard_fail")
        self.assertTrue(any("blocked marker" in item for item in report["errors"]))

    def test_evaluate_publish_source_returns_publishable_for_valid_source(self):
        report = evaluate_publish_source(
            {
                "title": "12화. 계약의 대가",
                "content": "유효한 본문 " * 80,
            }
        )
        self.assertEqual(report["status"], "publishable")
        self.assertEqual(report["errors"], [])
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_quality -v`

Expected: FAIL because `core/publishing_quality.py` does not exist yet.

- [ ] **Step 3: Write the minimal quality implementation**

Create `core/publishing_quality.py` with:

- `evaluate_publish_source(source_payload: dict) -> dict`
- internally call `validate_origin_draft(...)`
- map raw origin quality result to:
  - `publishable` when validation passes
  - `hard_fail` when validation fails
- include raw errors and a small `signals` dict

Do not add speculative `retry_possible` heuristics yet. Reserve the enum value for future gates.

- [ ] **Step 4: Re-run the focused tests to verify they pass**

Run: `python3 -m unittest tests.test_publishing_quality -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/publishing_quality.py tests/test_publishing_quality.py
git commit -m "feat: add publishing quality gate wrapper"
```

## Chunk 2: Add incident and Canon control boundaries

### Task 3: Add failing tests for publishing incident summarization

**Files:**
- Create: `tests/test_publishing_incidents.py`
- Create: `core/publishing_incidents.py`

- [ ] **Step 1: Write the failing incident tests**

```python
import unittest

from core.publishing_incidents import summarize_publish_attempt


class TestPublishingIncidents(unittest.TestCase):
    def test_summarize_publish_attempt_marks_done_and_idle_when_all_selected_targets_succeed(self):
        summary = summarize_publish_attempt(
            job={"targets": {"munpia": {"selected": True, "status": "done"}}},
            platform_results={"munpia": {"status": "done", "success": True}},
        )
        self.assertEqual(summary["job_status"], "done")
        self.assertEqual(summary["runtime_status"], "idle")
        self.assertEqual(summary["incident_type"], "")

    def test_summarize_publish_attempt_marks_paused_for_requires_user_action(self):
        summary = summarize_publish_attempt(
            job={"targets": {"munpia": {"selected": True, "status": "failed"}}},
            platform_results={
                "munpia": {
                    "status": "failed",
                    "success": False,
                    "error_type": "requires_user_action",
                    "error_text": "captcha required",
                }
            },
        )
        self.assertEqual(summary["runtime_status"], "paused")
        self.assertEqual(summary["incident_type"], "credential_incident")

    def test_summarize_publish_attempt_marks_partial_failed_when_results_are_mixed(self):
        summary = summarize_publish_attempt(
            job={
                "targets": {
                    "munpia": {"selected": True, "status": "done"},
                    "novelpia": {"selected": True, "status": "failed"},
                }
            },
            platform_results={
                "munpia": {"status": "done", "success": True},
                "novelpia": {"status": "failed", "success": False, "error_type": "retryable", "error_text": "timeout"},
            },
        )
        self.assertEqual(summary["job_status"], "partial_failed")
        self.assertEqual(summary["runtime_status"], "cooldown")
        self.assertEqual(summary["incident_type"], "platform_incident")
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_incidents -v`

Expected: FAIL because `core/publishing_incidents.py` does not exist yet.

- [ ] **Step 3: Write the minimal incident implementation**

Create `core/publishing_incidents.py` with:

- `summarize_publish_attempt(*, job: dict, platform_results: dict) -> dict`
- output fields:
  - `job_status`
  - `runtime_status`
  - `incident_type`
  - `needs_user_action`
  - `last_error`
- rules:
  - all selected targets done -> `done`, `idle`
  - some done -> `partial_failed`, `cooldown`
  - `requires_user_action` anywhere -> `paused`
  - no successes -> `failed`
  - map `requires_user_action` to `credential_incident`
  - map retryable/permanent upload failure to `platform_incident`

- [ ] **Step 4: Re-run the focused tests to verify they pass**

Run: `python3 -m unittest tests.test_publishing_incidents -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/publishing_incidents.py tests/test_publishing_incidents.py
git commit -m "feat: add publishing incident summarizer"
```

### Task 4: Add failing tests for Canon finalize logic

**Files:**
- Create: `tests/test_publishing_canon.py`
- Create: `core/publishing_canon.py`

- [ ] **Step 1: Write the failing Canon tests**

```python
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import core.canon_store as canon_store_module
import core.episode_artifact_store as episode_artifact_store_module
from core.canon_store import CanonStore
from core.episode_artifact_store import EpisodeArtifactStore
from core.publishing_canon import finalize_publish_canon


class TestPublishingCanon(unittest.TestCase):
    def test_finalize_publish_canon_prefers_result_candidate(self):
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

    def test_finalize_publish_canon_prefers_artifact_before_extractor(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(canon_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)), patch.object(
            episode_artifact_store_module, "DATA_PROJECTS_DIR", Path(tmpdir)
        ):
            EpisodeArtifactStore(project_name="sample").save_canon_update("ep_012", {"timeline": ["artifact"]})
            store = CanonStore(project_name="sample")
            report = finalize_publish_canon(
                project_name="sample",
                episode_id="ep_012",
                overall_status="done",
                job={},
                result={},
                source_payload={"content": "본문", "canon_update": {"timeline": ["artifact"]}},
                canon_store=store,
                now=datetime(2026, 3, 16, 21, 0),
            )
            self.assertEqual(report["source"], "artifact")

    def test_finalize_publish_canon_skips_when_publish_failed(self):
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
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_canon -v`

Expected: FAIL because `core/publishing_canon.py` does not exist yet.

- [ ] **Step 3: Write the minimal Canon implementation**

Create `core/publishing_canon.py` with:

- `finalize_publish_canon(...) -> dict`
- resolve candidate priority:
  - `result["canon_update"]`
  - `job["canon_update"]`
  - `source_payload["canon_update"]`
  - extractor fallback on `source_payload["content"]`
- apply Canon only when:
  - `overall_status == "done"`
  - `episode_id` is non-empty
  - candidate is non-empty after normalization
- append Canon event and write Canon snapshot when applied
- return a report with:
  - `status`
  - `source`
  - `candidate`
  - `error`

- [ ] **Step 4: Re-run the focused tests to verify they pass**

Run: `python3 -m unittest tests.test_publishing_canon -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/publishing_canon.py tests/test_publishing_canon.py
git commit -m "feat: add publishing canon finalizer"
```

## Chunk 3: Rewire publishing runtime around the new boundaries

### Task 5: Add failing runtime orchestration tests for the new control plane

**Files:**
- Modify: `tests/test_publishing_runtime.py`
- Modify: `core/publishing_runtime.py`

- [ ] **Step 1: Add failing runtime tests for helper-based orchestration**

Add tests in `tests/test_publishing_runtime.py` for:

```python
def test_tick_skips_when_policy_returns_skip():
    ...

def test_tick_records_hard_fail_quality_without_calling_executor():
    ...

def test_tick_uses_incident_summary_to_set_runtime_and_job_status():
    ...

def test_tick_delegates_canon_finalize_after_successful_publish():
    ...
```

These tests should patch:

- `select_runnable_job`
- `evaluate_publish_source`
- `summarize_publish_attempt`
- `finalize_publish_canon`

and assert that `PublishingRuntime.tick(...)` orchestrates them in order.

- [ ] **Step 2: Run the focused runtime tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_runtime -v`

Expected: FAIL because `PublishingRuntime` still owns the old logic directly.

- [ ] **Step 3: Rewire the runtime to use the new modules**

Modify `core/publishing_runtime.py` to:

- import and use:
  - `select_runnable_job`
  - `evaluate_publish_source`
  - `summarize_publish_attempt`
  - `finalize_publish_canon`
- keep `PublishingRuntime.tick(...)` as coordinator only
- preserve:
  - input snapshot write
  - publish result snapshot write
  - history append
  - queue/runtime/config persistence
- replace direct quality branching with standardized quality result handling
- replace direct incident branching with incident summary output
- replace direct Canon gating helper with `finalize_publish_canon(...)`

For quality result handling in this step:

- `publishable` -> proceed to executor
- `retry_possible` -> mark job failed for now but preserve the enum for later expansion
- `hard_fail` -> do not call executor; set runtime status according to a minimal quality incident rule

- [ ] **Step 4: Re-run the focused runtime tests to verify they pass**

Run: `python3 -m unittest tests.test_publishing_runtime -v`

Expected: PASS

- [ ] **Step 5: Run the broader publishing regression suite**

Run: `python3 -m unittest tests.test_publishing_policy tests.test_publishing_quality tests.test_publishing_incidents tests.test_publishing_canon tests.test_publishing_runtime tests.test_publishing_executor -v`

Expected: PASS

- [ ] **Step 6: Run the origin pipeline regression suite**

Run: `python3 -m unittest tests.test_story_bible_store tests.test_context_state_store tests.test_plot_store tests.test_canon_store tests.test_release_policy_store tests.test_episode_artifact_store tests.test_run_snapshot_store tests.test_origin_quality tests.test_context_manager tests.test_generator_storage tests.test_chapter_source tests.test_automation_store tests.test_automation_runtime tests.test_automation_ui tests.test_diagnostics_ui tests.test_automator tests.test_canon_extractor tests.test_publishing_executor tests.test_publishing_runtime tests.test_token_budget tests.test_ui_helpers tests.test_reviewer -v`

Expected: PASS

- [ ] **Step 7: Run syntax verification**

Run: `python3 -m py_compile core/publishing_policy.py core/publishing_quality.py core/publishing_incidents.py core/publishing_canon.py core/publishing_runtime.py tests/test_publishing_policy.py tests/test_publishing_quality.py tests/test_publishing_incidents.py tests/test_publishing_canon.py tests/test_publishing_runtime.py`

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add core/publishing_policy.py core/publishing_quality.py core/publishing_incidents.py core/publishing_canon.py core/publishing_runtime.py tests/test_publishing_policy.py tests/test_publishing_quality.py tests/test_publishing_incidents.py tests/test_publishing_canon.py tests/test_publishing_runtime.py
git commit -m "feat: add publish control plane v1"
```

## Chunk 4: Tighten runtime/UI integration around the new control-plane states

### Task 6: Add failing tests for cooldown and blocked runtime visibility

**Files:**
- Modify: `tests/test_publishing_runtime.py`
- Modify: `ui/publishing.py`
- Modify: `tests/test_publishing_ui.py`

- [ ] **Step 1: Add failing tests for new runtime state visibility**

Add tests that lock in:

- `cooldown` runtime state formatting in the publishing UI
- `blocked` runtime state formatting in the publishing UI
- runtime persistence of these statuses after incident summarization

- [ ] **Step 2: Run the focused UI/runtime tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_runtime tests.test_publishing_ui -v`

Expected: FAIL because the new states are not fully surfaced yet.

- [ ] **Step 3: Write the minimal UI/runtime integration**

Modify `ui/publishing.py` to:

- surface `cooldown` and `blocked` in any runtime status formatter
- keep existing `paused` controls intact
- avoid adding new workflow tabs or broad UI changes

Modify runtime persistence only as needed so those states can be observed in tests and history.

- [ ] **Step 4: Re-run the focused UI/runtime tests to verify they pass**

Run: `python3 -m unittest tests.test_publishing_runtime tests.test_publishing_ui -v`

Expected: PASS

- [ ] **Step 5: Run a final targeted regression**

Run: `python3 -m unittest tests.test_publishing_policy tests.test_publishing_quality tests.test_publishing_incidents tests.test_publishing_canon tests.test_publishing_runtime tests.test_publishing_ui tests.test_publishing_executor -v`

Expected: PASS

- [ ] **Step 6: Run final syntax verification**

Run: `python3 -m py_compile ui/publishing.py tests/test_publishing_ui.py tests/test_publishing_runtime.py`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add ui/publishing.py tests/test_publishing_ui.py tests/test_publishing_runtime.py
git commit -m "feat: surface publish control plane states"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-16-publish-control-plane-v1.md`. Ready to execute?
