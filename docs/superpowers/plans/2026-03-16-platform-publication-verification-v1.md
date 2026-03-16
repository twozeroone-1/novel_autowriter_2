# Platform Publication Verification V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add minimum adapter-side publication verification so successful upload requests are only treated as final platform success after one immediate verification pass.

**Architecture:** Extend the platform client contract with `verify_publication(expected)` and keep the verification logic inside adapters. `PublishingExecutor` calls verification after upload success and records the verification result in platform results. No runtime polling or delayed re-check loops in this slice.

**Tech Stack:** Python, unittest, existing platform clients, publishing executor, platform error/result dataclasses

---

## File Structure

### Modified files

- `core/platform_clients/base.py`
  - add adapter verification contract
- `core/platform_clients/munpia.py`
  - immediate post-upload verification logic
- `core/platform_clients/novelpia.py`
  - immediate post-upload verification logic
- `core/publishing_executor.py`
  - call verification and persist verification details
- `tests/test_platform_client_base.py`
  - contract sanity
- `tests/test_munpia_client.py`
  - Munpia verification tests
- `tests/test_novelpia_client.py`
  - Novelpia verification tests
- `tests/test_publishing_executor.py`
  - executor verification integration tests

## Chunk 1: Add the adapter verification contract

### Task 1: Add failing adapter tests first

**Files:**
- Modify: `tests/test_munpia_client.py`
- Modify: `tests/test_novelpia_client.py`
- Modify: `core/platform_clients/base.py`
- Modify: `core/platform_clients/munpia.py`
- Modify: `core/platform_clients/novelpia.py`

- [ ] **Step 1: Add failing Munpia/Novelpia verification tests**

Add tests that lock:

- Munpia verification succeeds when current URL is a completed episode page
- Munpia verification fails retryably when still on the editor URL
- Novelpia verification succeeds on a viewer URL
- Novelpia verification fails retryably on editor or `write_proc`

- [ ] **Step 2: Run the focused client tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_munpia_client tests.test_novelpia_client -v
```

Expected: FAIL because `verify_publication(...)` does not exist yet.

- [ ] **Step 3: Implement the verification contract**

Update:

- `core/platform_clients/base.py`
- `core/platform_clients/munpia.py`
- `core/platform_clients/novelpia.py`

Rules:

- keep `expected` as dict in v1
- return `PlatformActionResult(status="done", success=True, ...)` on verification success
- return `PlatformError(..., error_type="retryable")` when verification cannot confirm publication

- [ ] **Step 4: Re-run the focused client tests**

Run:

```bash
python3 -m unittest tests.test_munpia_client tests.test_novelpia_client -v
```

Expected: PASS

- [ ] **Step 5: Commit chunk 1**

```bash
git add core/platform_clients/base.py core/platform_clients/munpia.py core/platform_clients/novelpia.py
git add tests/test_munpia_client.py tests/test_novelpia_client.py
git commit -m "feat: add platform publication verification"
```

## Chunk 2: Integrate verification into executor

### Task 2: Add executor tests first

**Files:**
- Modify: `core/publishing_executor.py`
- Modify: `tests/test_publishing_executor.py`

- [ ] **Step 1: Add failing executor verification tests**

Add tests that lock:

- executor calls `verify_publication(...)` after upload success
- verification failure downgrades final platform result to failed
- final result includes nested `verification` payload

- [ ] **Step 2: Run the focused executor tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_publishing_executor -v
```

Expected: FAIL because executor does not yet verify uploads.

- [ ] **Step 3: Implement executor verification**

Update `core/publishing_executor.py`:

- build `expected_publication` from packaged expectation plus actual `work_id` and `episode_id`
- call `client.verify_publication(expected_publication)` after successful upload
- mark final platform success only if verification succeeds
- store nested `verification` payload in `platform_results`

- [ ] **Step 4: Re-run the focused executor tests**

Run:

```bash
python3 -m unittest tests.test_publishing_executor tests.test_munpia_client tests.test_novelpia_client -v
```

Expected: PASS

- [ ] **Step 5: Commit chunk 2**

```bash
git add core/publishing_executor.py tests/test_publishing_executor.py
git commit -m "feat: verify publication after platform upload"
```

## Chunk 3: Regression verification

### Task 3: Run regressions and syntax checks

**Files:**
- No new files; verification only

- [ ] **Step 1: Run focused adapter/executor regressions**

Run:

```bash
python3 -m unittest \
  tests.test_platform_client_base \
  tests.test_munpia_client \
  tests.test_novelpia_client \
  tests.test_publishing_executor -v
```

Expected: PASS

- [ ] **Step 2: Run broader origin/publishing regressions**

Run:

```bash
python3 -m unittest \
  tests.test_story_bible_store \
  tests.test_context_state_store \
  tests.test_plot_store \
  tests.test_canon_store \
  tests.test_release_policy_store \
  tests.test_episode_artifact_store \
  tests.test_run_snapshot_store \
  tests.test_origin_quality \
  tests.test_context_manager \
  tests.test_generator_storage \
  tests.test_generator_planning \
  tests.test_chapter_source \
  tests.test_automation_store \
  tests.test_automation_runtime \
  tests.test_automation_ui \
  tests.test_diagnostics_ui \
  tests.test_automator \
  tests.test_canon_extractor \
  tests.test_publishing_executor \
  tests.test_release_policy_engine \
  tests.test_publishing_policy \
  tests.test_publishing_runtime \
  tests.test_publishing_structure \
  tests.test_quality_gate_orchestrator \
  tests.test_publishing_quality \
  tests.test_publishing_incidents \
  tests.test_publishing_canon \
  tests.test_publishing_critic \
  tests.test_publish_packager \
  tests.test_platform_client_base \
  tests.test_munpia_client \
  tests.test_novelpia_client \
  tests.test_token_budget \
  tests.test_ui_helpers \
  tests.test_reviewer \
  tests.test_planner \
  tests.test_episode_planner -v
```

Expected: PASS

- [ ] **Step 3: Run syntax and diff checks**

Run:

```bash
python3 -m py_compile \
  core/platform_clients/base.py \
  core/platform_clients/munpia.py \
  core/platform_clients/novelpia.py \
  core/publishing_executor.py \
  tests/test_platform_client_base.py \
  tests/test_munpia_client.py \
  tests/test_novelpia_client.py \
  tests/test_publishing_executor.py

git diff --check -- \
  core/platform_clients/base.py \
  core/platform_clients/munpia.py \
  core/platform_clients/novelpia.py \
  core/publishing_executor.py \
  tests/test_platform_client_base.py \
  tests/test_munpia_client.py \
  tests/test_novelpia_client.py \
  tests/test_publishing_executor.py
```

Expected: no syntax or whitespace errors
