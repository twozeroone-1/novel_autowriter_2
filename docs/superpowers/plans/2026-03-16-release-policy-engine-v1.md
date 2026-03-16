# Release Policy Engine v1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real release policy engine that enforces per-platform daily release caps, same-day second-release gating, and cooldown/blocked policy behavior before the publishing runtime selects and executes a job.

**Architecture:** Introduce a dedicated `release_policy_engine.py` that evaluates platform slot availability from release policy, runtime state, and recent publishing history. Keep `publishing_policy.py` focused on queue selection, then rewire `publishing_runtime.py` to run `policy engine -> queue selection -> quality -> executor -> incidents -> canon` while preserving current snapshots and history writes.

**Tech Stack:** Python, unittest, existing `PublishingStore`, `ReleasePolicyStore`, `PublishingRuntime`, `PublishingExecutor`, `PublishingStore.load_recent_history`, `automation_scheduler.is_schedule_due`

---

## File Structure

### New files

- `core/release_policy_engine.py`
  - Evaluates whether a publish slot is currently open and which platforms are policy-allowed.
- `tests/test_release_policy_engine.py`
  - Direct unit tests for per-platform caps, burst locking, cooldown, blocked, and paused behavior.

### Modified files

- `core/publishing_policy.py`
  - Narrow from schedule-aware selector to queue-only selector that chooses the first job compatible with policy-allowed platforms.
- `tests/test_publishing_policy.py`
  - Replace old schedule/runtime gating tests with queue-selection contract tests.
- `core/publishing_runtime.py`
  - Load release policy, evaluate it before queue selection, pass allowed platforms to selector, and filter executor targets accordingly.
- `tests/test_publishing_runtime.py`
  - Add coordinator tests for policy skip, allowed-platform filtering, and runtime persistence through policy decisions.

### Existing files to reference

- `core/release_policy_store.py`
- `core/publishing_store.py`
- `core/publishing_executor.py`
- `core/publishing_incidents.py`
- `core/publishing_quality.py`
- `core/publishing_canon.py`
- `core/automation_scheduler.py`
- `tests/test_release_policy_store.py`
- `tests/test_publishing_executor.py`

## Chunk 1: Add Release Policy Engine and narrow queue selection

### Task 1: Add failing tests for the release policy engine

**Files:**
- Create: `tests/test_release_policy_engine.py`
- Create: `core/release_policy_engine.py`

- [ ] **Step 1: Write the failing engine tests**

```python
import unittest
from datetime import datetime, timezone

from core.release_policy_engine import evaluate_release_policy


class TestReleasePolicyEngine(unittest.TestCase):
    def test_evaluate_release_policy_skips_when_runtime_is_paused(self):
        decision = evaluate_release_policy(
            policy={"global": {"burst_allowed": False}, "platforms": {"munpia": {"enabled": True, "max_daily_releases": 1}}},
            runtime={"status": "paused", "last_run_at": None},
            history=[],
            now=datetime(2026, 3, 16, 21, 0, tzinfo=timezone.utc),
            force=False,
        )
        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "paused")

    def test_evaluate_release_policy_locks_burst_slot_until_first_same_day_success(self):
        decision = evaluate_release_policy(
            policy={
                "global": {"burst_allowed": True},
                "platforms": {"munpia": {"enabled": True, "max_daily_releases": 2}},
            },
            runtime={"status": "idle", "last_run_at": None},
            history=[],
            now=datetime(2026, 3, 16, 21, 0, tzinfo=timezone.utc),
            force=False,
        )
        self.assertEqual(decision["action"], "run_now")
        self.assertFalse(decision["burst_slot"])
        self.assertEqual(decision["allowed_platforms"], ["munpia"])

    def test_evaluate_release_policy_opens_second_slot_after_first_same_day_success(self):
        history = [
            {
                "timestamp": "2026-03-16T09:00:00+00:00",
                "success": True,
                "platform_results": {"munpia": {"success": True, "status": "done"}},
            }
        ]
        decision = evaluate_release_policy(
            policy={
                "global": {"burst_allowed": True},
                "platforms": {"munpia": {"enabled": True, "max_daily_releases": 2}},
            },
            runtime={"status": "idle", "last_run_at": "2026-03-16T09:00:00+00:00"},
            history=history,
            now=datetime(2026, 3, 16, 21, 0, tzinfo=timezone.utc),
            force=False,
        )
        self.assertEqual(decision["action"], "run_now")
        self.assertTrue(decision["burst_slot"])

    def test_evaluate_release_policy_blocks_after_quality_hard_fail(self):
        decision = evaluate_release_policy(
            policy={"global": {"burst_allowed": False}, "platforms": {"munpia": {"enabled": True, "max_daily_releases": 1}}},
            runtime={"status": "blocked", "last_run_at": "2026-03-16T21:00:00+00:00", "last_error": "bad title"},
            history=[],
            now=datetime(2026, 3, 16, 21, 5, tzinfo=timezone.utc),
            force=False,
        )
        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "blocked")

    def test_evaluate_release_policy_cools_down_until_next_schedule_window(self):
        decision = evaluate_release_policy(
            policy={"global": {"burst_allowed": False}, "platforms": {"munpia": {"enabled": True, "max_daily_releases": 1}}},
            runtime={"status": "cooldown", "last_run_at": "2026-03-16T20:30:00+00:00"},
            history=[],
            now=datetime(2026, 3, 16, 20, 45, tzinfo=timezone.utc),
            force=False,
            schedule={"type": "daily", "time": "21:00"},
        )
        self.assertEqual(decision["action"], "skip")
        self.assertEqual(decision["reason"], "cooldown")
```

- [ ] **Step 2: Run the focused engine tests to verify they fail**

Run: `python3 -m unittest tests.test_release_policy_engine -v`

Expected: FAIL because `core/release_policy_engine.py` does not exist yet.

- [ ] **Step 3: Write the minimal engine implementation**

Create `core/release_policy_engine.py` with:

- `evaluate_release_policy(*, policy: dict, runtime: dict, history: list[dict], now: datetime, force: bool, schedule: dict | None = None) -> dict`
- small helpers:
  - `_collect_today_platform_success_counts(...)`
  - `_platform_is_allowed_now(...)`
  - `_is_second_slot_open(...)`
- return shape:

```python
{
    "action": "run_now" | "skip",
    "reason": "",
    "allowed_platforms": [...],
    "blocked_platforms": {...},
    "burst_slot": False,
    "next_runtime_status": "idle" | "cooldown" | "blocked" | "paused",
}
```

Rules for the minimal implementation:

- `paused` and `blocked` skip immediately
- `cooldown` skips unless `force=True` or the schedule window is open again
- platform usage counts come only from successful same-day `platform_results`
- a second same-day slot opens only when:
  - `global.burst_allowed` is true
  - `platform.max_daily_releases >= 2`
  - there is already one successful publish for that platform on that day
- if a platform already hit its cap, add a per-platform reason such as `daily_limit_reached`

- [ ] **Step 4: Re-run the focused engine tests to verify they pass**

Run: `python3 -m unittest tests.test_release_policy_engine -v`

Expected: PASS

### Task 2: Rewrite `publishing_policy.py` into a pure queue selector

**Files:**
- Modify: `core/publishing_policy.py`
- Modify: `tests/test_publishing_policy.py`

- [ ] **Step 1: Rewrite the selector tests around policy-compatible queue selection**

Replace the old schedule/runtime tests with queue-only tests such as:

```python
def test_select_runnable_job_returns_first_job_with_allowed_selected_target(self):
    decision = select_runnable_job(
        queue=[
            {"id": "job-1", "status": "pending", "targets": {"munpia": {"selected": True}}},
            {"id": "job-2", "status": "pending", "targets": {"novelpia": {"selected": True}}},
        ],
        allowed_platforms={"novelpia"},
    )
    self.assertEqual(decision["action"], "run_now")
    self.assertEqual(decision["job"]["id"], "job-2")

def test_select_runnable_job_skips_when_no_job_matches_allowed_platforms(self):
    decision = select_runnable_job(
        queue=[{"id": "job-1", "status": "pending", "targets": {"munpia": {"selected": True}}}],
        allowed_platforms={"novelpia"},
    )
    self.assertEqual(decision["action"], "skip")
    self.assertEqual(decision["reason"], "no_job")
```

- [ ] **Step 2: Run the selector tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_policy -v`

Expected: FAIL because `select_runnable_job(...)` still expects config/runtime/now and still owns schedule gating.

- [ ] **Step 3: Rewrite the minimal selector implementation**

Modify `core/publishing_policy.py` so that:

- signature becomes `select_runnable_job(*, queue: list[dict], allowed_platforms: set[str]) -> dict`
- it scans `pending` and `partial_failed` jobs in queue order
- it returns the first job with at least one selected target inside `allowed_platforms`
- it returns `{"action": "skip", "reason": "no_job", "job": None}` if none match

Do not keep schedule, enabled, paused, or running checks here after this refactor.

- [ ] **Step 4: Re-run the focused selector tests**

Run: `python3 -m unittest tests.test_publishing_policy tests.test_release_policy_engine -v`

Expected: PASS

- [ ] **Step 5: Commit chunk 1**

```bash
git add core/release_policy_engine.py core/publishing_policy.py tests/test_release_policy_engine.py tests/test_publishing_policy.py
git commit -m "feat: add release policy engine core"
```

## Chunk 2: Rewire the publishing runtime around the policy engine

### Task 3: Add failing runtime tests for policy-first orchestration

**Files:**
- Modify: `tests/test_publishing_runtime.py`
- Modify: `core/publishing_runtime.py`

- [ ] **Step 1: Add failing coordinator tests**

Add tests that patch the new engine and selector boundaries:

```python
def test_tick_skips_when_release_policy_engine_returns_skip(self):
    ...

def test_tick_passes_allowed_platforms_into_queue_selector(self):
    ...

def test_tick_filters_executor_job_targets_to_allowed_platforms(self):
    ...

def test_tick_force_bypasses_schedule_but_not_blocked_policy(self):
    ...
```

The new tests should patch:

- `ReleasePolicyStore.load`
- `evaluate_release_policy`
- `select_runnable_job`

and then assert:

- executor is not called when policy says skip
- selector receives `allowed_platforms`
- executor sees only the policy-allowed selected targets
- runtime state/history continue to be written after a policy-approved run

- [ ] **Step 2: Run the focused runtime tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_runtime -v`

Expected: FAIL because `PublishingRuntime` does not load release policy or call the new engine yet.

- [ ] **Step 3: Rewire the runtime**

Modify `core/publishing_runtime.py` to:

- instantiate `ReleasePolicyStore` in `PublishingRuntime.__init__(...)`
- load recent history before queue selection
- call `evaluate_release_policy(...)` before `select_runnable_job(...)`
- pass `schedule=config.get("schedule", {})` and `force=force` into the engine
- pass `allowed_platforms=set(policy_decision["allowed_platforms"])` into `select_runnable_job(...)`
- build an executor payload filtered to only policy-allowed selected targets
- write `policy_decision` into the input snapshot for traceability

Minimal runtime integration pattern:

```python
policy = self.release_policy_store.load()
history = self.store.load_recent_history(limit=200)
policy_decision = evaluate_release_policy(...)
if policy_decision["action"] != "run_now":
    return

job_decision = select_runnable_job(queue=queue, allowed_platforms=set(policy_decision["allowed_platforms"]))
```

Add a small helper such as `_build_executor_job(job, allowed_platforms)` if needed. Keep `PublishingRuntime` coordinator-oriented.

- [ ] **Step 4: Re-run the focused runtime tests**

Run: `python3 -m unittest tests.test_publishing_runtime -v`

Expected: PASS

### Task 4: Run publishing-focused regressions

**Files:**
- No new files; verification only

- [ ] **Step 1: Run the focused publishing regression suite**

Run: `python3 -m unittest tests.test_release_policy_engine tests.test_publishing_policy tests.test_publishing_runtime tests.test_publishing_quality tests.test_publishing_incidents tests.test_publishing_canon tests.test_publishing_executor -v`

Expected: PASS

- [ ] **Step 2: Run syntax verification for touched modules**

Run: `python3 -m py_compile core/release_policy_engine.py core/publishing_policy.py core/publishing_runtime.py tests/test_release_policy_engine.py tests/test_publishing_policy.py tests/test_publishing_runtime.py`

Expected: PASS

- [ ] **Step 3: Commit chunk 2**

```bash
git add core/publishing_runtime.py tests/test_publishing_runtime.py
git commit -m "feat: wire runtime to release policy engine"
```

## Chunk 3: Full regression and cleanup verification

### Task 5: Run broader project regression and inspect residual risks

**Files:**
- No new files; verification only

- [ ] **Step 1: Run the origin/publishing regression suite**

Run: `python3 -m unittest tests.test_story_bible_store tests.test_context_state_store tests.test_plot_store tests.test_canon_store tests.test_release_policy_store tests.test_episode_artifact_store tests.test_run_snapshot_store tests.test_origin_quality tests.test_context_manager tests.test_generator_storage tests.test_chapter_source tests.test_automation_store tests.test_automation_runtime tests.test_automation_ui tests.test_diagnostics_ui tests.test_automator tests.test_canon_extractor tests.test_publishing_executor tests.test_release_policy_engine tests.test_publishing_policy tests.test_publishing_runtime tests.test_publishing_quality tests.test_publishing_incidents tests.test_publishing_canon tests.test_token_budget tests.test_ui_helpers tests.test_reviewer -v`

Expected: PASS

- [ ] **Step 2: Inspect diff scope for policy-related files only**

Run:

```bash
git diff --stat -- core/release_policy_engine.py core/publishing_policy.py core/publishing_runtime.py tests/test_release_policy_engine.py tests/test_publishing_policy.py tests/test_publishing_runtime.py
git diff --check -- core/release_policy_engine.py core/publishing_policy.py core/publishing_runtime.py tests/test_release_policy_engine.py tests/test_publishing_policy.py tests/test_publishing_runtime.py
```

Expected:

- diff is limited to the intended policy/runtime slice
- no whitespace errors

- [ ] **Step 3: Summarize residual non-goals before execution handoff**

Record explicitly in the execution summary if any of these remain intentionally unimplemented:

- project-wide total daily cap
- dedicated policy ledger
- third-slot or arbitrary burst logic
- long-term `stopped` state

- [ ] **Step 4: No additional commit unless verification forces a fix**

If no fixes are required after the full regression suite, stop here and hand off to execution completion.

Plan complete and saved to `docs/superpowers/plans/2026-03-16-release-policy-engine-v1.md`. Ready to execute?
