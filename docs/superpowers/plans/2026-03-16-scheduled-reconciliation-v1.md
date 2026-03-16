# Scheduled Reconciliation V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a due-time follow-up verification path for reserved uploads so scheduled jobs can later resolve to real publication before Canon finalize.

**Architecture:** Keep the existing publish path intact and add a narrow scheduled reconciliation path. `PublishingRuntime` should detect due scheduled jobs before normal publish selection, `PublishingExecutor` should verify scheduled targets without re-uploading, and `NovelpiaClient` should confirm publication from a listing page once the reserved time has passed.

**Tech Stack:** Python, unittest, existing publish control plane modules, Playwright-backed platform clients, JSON queue/history snapshots

---

## File Structure

### Modified files

- `core/platform_clients/novelpia.py`
  - add reserved follow-up verification from listing content
- `core/publishing_policy.py`
  - select due scheduled jobs before normal pending jobs
- `core/publishing_executor.py`
  - add `reconcile_scheduled_job(...)`
- `core/publishing_incidents.py`
  - distinguish `scheduled` from `done`
- `core/publishing_runtime.py`
  - add scheduled-first runtime flow and Canon gating
- `tests/test_novelpia_client.py`
- `tests/test_publishing_policy.py`
- `tests/test_publishing_executor.py`
- `tests/test_publishing_incidents.py`
- `tests/test_publishing_runtime.py`

## Chunk 1: Add failing tests for scheduled reconciliation boundaries

### Task 1: Write the red tests

**Files:**
- Modify: `tests/test_novelpia_client.py`
- Modify: `tests/test_publishing_policy.py`
- Modify: `tests/test_publishing_executor.py`
- Modify: `tests/test_publishing_incidents.py`
- Modify: `tests/test_publishing_runtime.py`

- [ ] **Step 1: Add failing Novelpia follow-up verification tests**

Add tests proving:

- reserved follow-up verification returns `done` when the work listing contains the expected episode title
- reserved follow-up verification raises `retryable` when the title is still absent after `reserved_at`

- [ ] **Step 2: Add failing policy/executor/incident/runtime tests**

Add tests proving:

- due scheduled jobs are selected before normal pending jobs
- `reconcile_scheduled_job(...)` verifies without calling `upload_episode(...)`
- all-scheduled selected targets produce `job_status="scheduled"` and `runtime_status="scheduled"`
- runtime leaves initial reserved upload in `scheduled`
- runtime later resolves a due scheduled job to `done` and applies Canon

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_novelpia_client tests.test_publishing_policy tests.test_publishing_executor tests.test_publishing_incidents tests.test_publishing_runtime -v
```

Expected: FAIL on missing scheduled reconciliation behavior.

## Chunk 2: Implement scheduled selection and executor reconciliation

### Task 2: Add minimal runtime/executor support

**Files:**
- Modify: `core/publishing_policy.py`
- Modify: `core/publishing_executor.py`
- Modify: `core/publishing_runtime.py`
- Modify: `tests/test_publishing_policy.py`
- Modify: `tests/test_publishing_executor.py`
- Modify: `tests/test_publishing_runtime.py`

- [ ] **Step 1: Teach policy selection about due scheduled jobs**

Implement the smallest selection change that:

- inspects jobs with `status == "scheduled"`
- checks selected targets with `status == "scheduled"`
- treats `reserved_at <= now` as due
- returns a mode that runtime can treat as scheduled reconciliation

- [ ] **Step 2: Add `reconcile_scheduled_job(...)` to executor**

Implement a second executor path that:

- loads the selected scheduled targets
- logs in
- calls `verify_publication(...)`
- does not call `ensure_work(...)` or `upload_episode(...)`
- returns `platform_results` in the same shape as normal publish execution

- [ ] **Step 3: Wire runtime to scheduled-first behavior**

Implement runtime changes so that:

- due scheduled jobs bypass normal release-slot selection
- initial `scheduled` outcomes persist as `job.status = "scheduled"` and `runtime.status = "scheduled"`
- later `done` reconciliation applies Canon

- [ ] **Step 4: Run focused tests and make them pass**

Run:

```bash
python3 -m unittest tests.test_publishing_policy tests.test_publishing_executor tests.test_publishing_runtime -v
```

Expected: PASS

## Chunk 3: Implement Novelpia follow-up verification and incident interpretation

### Task 3: Finish adapter/runtime semantics

**Files:**
- Modify: `core/platform_clients/novelpia.py`
- Modify: `core/publishing_incidents.py`
- Modify: `tests/test_novelpia_client.py`
- Modify: `tests/test_publishing_incidents.py`

- [ ] **Step 1: Add minimal Novelpia listing-page verification**

Implement reserved follow-up verification that:

- navigates to a work/listing URL when needed
- inspects content for the expected episode title
- returns `done` when found
- raises `retryable` when absent after due time

- [ ] **Step 2: Distinguish `scheduled` from `done` in incident summarization**

Implement the smallest change that:

- maps all-scheduled selected targets to `job_status="scheduled"`
- keeps `runtime_status="scheduled"`
- preserves existing mixed failure handling

- [ ] **Step 3: Re-run focused tests**

Run:

```bash
python3 -m unittest tests.test_novelpia_client tests.test_publishing_incidents -v
```

Expected: PASS

## Chunk 4: Verify and commit

### Task 4: Full slice verification

**Files:**
- Modify: all files above

- [ ] **Step 1: Run the established publishing/origin regression suite**

Run:

```bash
python3 -m unittest tests.test_api_key_store tests.test_app_paths tests.test_automation_runtime tests.test_automation_scheduler tests.test_automation_store tests.test_automation_ui tests.test_automator tests.test_backend_gate tests.test_canon_extractor tests.test_canon_store tests.test_chapter_source tests.test_context_characters tests.test_context_manager tests.test_context_prompt_sections tests.test_context_state_shadow tests.test_context_state_store tests.test_context_story_bible_shadow tests.test_episode_artifact_store tests.test_episode_planner tests.test_file_utils tests.test_generator_planning tests.test_generator_storage tests.test_llm_backends tests.test_origin_quality tests.test_platform_client_base tests.test_munpia_client tests.test_novelpia_client tests.test_platform_credentials tests.test_publish_packager tests.test_publishing_canon tests.test_publishing_critic tests.test_publishing_executor tests.test_publishing_incidents tests.test_publishing_policy tests.test_publishing_quality tests.test_publishing_regenerate tests.test_publishing_runtime tests.test_publishing_store tests.test_publishing_structure tests.test_publishing_ui tests.test_quality_gate_orchestrator tests.test_release_policy_engine tests.test_release_policy_store tests.test_reviewer tests.test_run_snapshot_store tests.test_story_bible_store tests.test_token_budget tests.test_ui_helpers -v
```

Expected: PASS

- [ ] **Step 2: Run syntax and diff verification**

Run:

```bash
python3 -m py_compile core/platform_clients/novelpia.py core/publishing_policy.py core/publishing_executor.py core/publishing_incidents.py core/publishing_runtime.py tests/test_novelpia_client.py tests/test_publishing_policy.py tests/test_publishing_executor.py tests/test_publishing_incidents.py tests/test_publishing_runtime.py
git diff --check -- core/platform_clients/novelpia.py core/publishing_policy.py core/publishing_executor.py core/publishing_incidents.py core/publishing_runtime.py tests/test_novelpia_client.py tests/test_publishing_policy.py tests/test_publishing_executor.py tests/test_publishing_incidents.py tests/test_publishing_runtime.py docs/superpowers/specs/2026-03-16-scheduled-reconciliation-v1-design.md docs/superpowers/plans/2026-03-16-scheduled-reconciliation-v1.md
```

Expected: clean output

- [ ] **Step 3: Commit the slice**

```bash
git add core/platform_clients/novelpia.py core/publishing_policy.py core/publishing_executor.py core/publishing_incidents.py core/publishing_runtime.py tests/test_novelpia_client.py tests/test_publishing_policy.py tests/test_publishing_executor.py tests/test_publishing_incidents.py tests/test_publishing_runtime.py
git commit -m "feat: add scheduled reconciliation flow"
```
