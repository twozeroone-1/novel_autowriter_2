# Publishing Smoke Test Command V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a non-destructive command that checks whether a project can log in to selected publishing platforms and reach the mapped work editor without uploading anything.

**Architecture:** Add one narrow smoke-check method to the adapter boundary, build a `publishing_smoke` runner that loads config and credentials and aggregates results, and expose it through a thin script that prints JSON and exits non-zero on failure. Keep queue/runtime/history out of scope.

**Tech Stack:** Python, unittest, existing platform clients, secure credential loader, Playwright-backed browser sessions

---

## File Structure

### Create

- `core/publishing_smoke.py`
  - aggregate non-destructive project/platform smoke checks
- `tests/test_publishing_smoke.py`
  - smoke runner behavior and failure-mode coverage
- `scripts/publishing_smoke.py`
  - thin CLI wrapper around the core runner

### Modify

- `core/platform_clients/base.py`
  - add smoke-check abstract contract
- `core/platform_clients/munpia.py`
  - implement editor smoke check
- `core/platform_clients/novelpia.py`
  - implement editor smoke check
- `tests/test_munpia_client.py`
- `tests/test_novelpia_client.py`

## Chunk 1: Add failing tests

### Task 1: Write the red tests

**Files:**
- Modify: `tests/test_munpia_client.py`
- Modify: `tests/test_novelpia_client.py`
- Create: `tests/test_publishing_smoke.py`

- [ ] **Step 1: Add failing adapter smoke tests**

Add tests proving:

- `MunpiaClient.smoke_check_editor(...)` succeeds when the editor selectors exist
- `NovelpiaClient.smoke_check_editor(...)` succeeds when the editor selectors exist

- [ ] **Step 2: Add failing runner tests**

Add tests proving:

- smoke runner returns success when a fake client logs in and editor check passes
- smoke runner fails when credentials are missing
- smoke runner fails when `work_id` is missing
- smoke runner respects explicit platform filtering

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_munpia_client tests.test_novelpia_client tests.test_publishing_smoke -v
```

Expected: FAIL on missing smoke contracts and runner.

## Chunk 2: Implement the minimal smoke path

### Task 2: Make the tests pass

**Files:**
- Modify: `core/platform_clients/base.py`
- Modify: `core/platform_clients/munpia.py`
- Modify: `core/platform_clients/novelpia.py`
- Create: `core/publishing_smoke.py`
- Create: `scripts/publishing_smoke.py`

- [ ] **Step 1: Add the base smoke-check contract**

Implement the smallest abstract method addition for `smoke_check_editor(work_id)`.

- [ ] **Step 2: Implement adapter smoke editor checks**

Implement the smallest safe checks so each client:

- navigates to the upload/editor URL for the given `work_id`
- verifies the required editor selectors exist
- returns success without uploading

- [ ] **Step 3: Implement the publishing smoke runner**

Implement the smallest runner that:

- loads config and credentials
- resolves selected platforms
- checks login + editor readiness
- returns a JSON-serializable report

- [ ] **Step 4: Implement the CLI wrapper**

Implement a thin script that:

- parses project name / platforms / headless flag
- calls the runner
- prints JSON
- exits 0/1 based on `success`

- [ ] **Step 5: Run focused tests and make them pass**

Run:

```bash
python3 -m unittest tests.test_munpia_client tests.test_novelpia_client tests.test_publishing_smoke -v
```

Expected: PASS

## Chunk 3: Verify and commit

### Task 3: Full slice verification

**Files:**
- Modify: all files above

- [ ] **Step 1: Run the established publishing regression subset**

Run:

```bash
python3 -m unittest tests.test_platform_client_base tests.test_munpia_client tests.test_novelpia_client tests.test_platform_credentials tests.test_publishing_smoke tests.test_publishing_executor tests.test_publishing_runtime tests.test_publishing_policy tests.test_publishing_incidents tests.test_publishing_ui -v
```

Expected: PASS

- [ ] **Step 2: Run syntax and diff verification**

Run:

```bash
python3 -m py_compile core/platform_clients/base.py core/platform_clients/munpia.py core/platform_clients/novelpia.py core/publishing_smoke.py scripts/publishing_smoke.py tests/test_munpia_client.py tests/test_novelpia_client.py tests/test_publishing_smoke.py
git diff --check -- core/platform_clients/base.py core/platform_clients/munpia.py core/platform_clients/novelpia.py core/publishing_smoke.py scripts/publishing_smoke.py tests/test_munpia_client.py tests/test_novelpia_client.py tests/test_publishing_smoke.py docs/superpowers/specs/2026-03-16-publishing-smoke-test-command-v1-design.md docs/superpowers/plans/2026-03-16-publishing-smoke-test-command-v1.md
```

Expected: clean output

- [ ] **Step 3: Commit the slice**

```bash
git add core/platform_clients/base.py core/platform_clients/munpia.py core/platform_clients/novelpia.py core/publishing_smoke.py scripts/publishing_smoke.py tests/test_munpia_client.py tests/test_novelpia_client.py tests/test_publishing_smoke.py docs/superpowers/specs/2026-03-16-publishing-smoke-test-command-v1-design.md docs/superpowers/plans/2026-03-16-publishing-smoke-test-command-v1.md
git commit -m "feat: add publishing smoke test command"
```
