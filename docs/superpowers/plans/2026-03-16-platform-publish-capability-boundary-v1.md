# Platform Publish Capability Boundary V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent unsupported publish-mode/platform combinations from entering the publishing queue by declaring publish-mode capabilities once and validating them in the UI.

**Architecture:** Add a narrow publish-mode capability contract at the platform client boundary and reuse it from the publishing UI. Keep executor/runtime validation unchanged so the new UI check becomes the first line of defense, not the only one.

**Tech Stack:** Python, unittest, existing platform client layer, Streamlit publishing UI helpers

---

## File Structure

### Modified files

- `core/platform_clients/base.py`
  - add the smallest shared publish-mode capability helper
- `core/platform_clients/munpia.py`
  - declare supported publish modes
- `core/platform_clients/novelpia.py`
  - declare supported publish modes
- `ui/publishing.py`
  - validate selected platforms against requested publish mode before queue append
- `tests/test_platform_client_base.py`
- `tests/test_munpia_client.py`
- `tests/test_novelpia_client.py`
- `tests/test_publishing_ui.py`

## Chunk 1: Add failing tests for capability metadata and UI validation

### Task 1: Write the red tests

**Files:**
- Modify: `tests/test_platform_client_base.py`
- Modify: `tests/test_munpia_client.py`
- Modify: `tests/test_novelpia_client.py`
- Modify: `tests/test_publishing_ui.py`

- [ ] **Step 1: Add failing platform capability tests**

Add tests proving:

- the base helper returns `("immediate",)` for Munpia
- the base helper returns `("immediate", "reserved")` for Novelpia

- [ ] **Step 2: Add failing publishing UI tests**

Add tests proving:

- UI helper reports Munpia as unsupported for `reserved`
- mixed Munpia/Novelpia selection is rejected for `reserved`
- mixed selection remains valid for `immediate`

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_platform_client_base tests.test_munpia_client tests.test_novelpia_client tests.test_publishing_ui -v
```

Expected: FAIL on missing capability boundary behavior.

## Chunk 2: Implement minimal capability declarations and UI validation

### Task 2: Make the tests pass

**Files:**
- Modify: `core/platform_clients/base.py`
- Modify: `core/platform_clients/munpia.py`
- Modify: `core/platform_clients/novelpia.py`
- Modify: `ui/publishing.py`

- [ ] **Step 1: Add the smallest shared capability helper**

Implement a narrow helper that can answer:

- supported publish modes for a platform name
- whether a platform supports a requested publish mode

- [ ] **Step 2: Declare supported modes on concrete clients**

Implement the smallest client changes so:

- Munpia only supports `immediate`
- Novelpia supports `immediate` and `reserved`

- [ ] **Step 3: Validate queue additions in the publishing UI**

Implement the smallest queue-editor change so:

- unsupported `reserved` combinations are blocked with a warning
- supported combinations continue to append the job exactly as before

- [ ] **Step 4: Run focused tests and make them pass**

Run:

```bash
python3 -m unittest tests.test_platform_client_base tests.test_munpia_client tests.test_novelpia_client tests.test_publishing_ui -v
```

Expected: PASS

## Chunk 3: Verify and commit

### Task 3: Full slice verification

**Files:**
- Modify: all files above

- [ ] **Step 1: Run the established publishing regression subset**

Run:

```bash
python3 -m unittest tests.test_platform_client_base tests.test_munpia_client tests.test_novelpia_client tests.test_publishing_ui tests.test_publishing_executor tests.test_publishing_runtime tests.test_publishing_policy tests.test_publishing_incidents -v
```

Expected: PASS

- [ ] **Step 2: Run syntax and diff verification**

Run:

```bash
python3 -m py_compile core/platform_clients/base.py core/platform_clients/munpia.py core/platform_clients/novelpia.py ui/publishing.py tests/test_platform_client_base.py tests/test_munpia_client.py tests/test_novelpia_client.py tests/test_publishing_ui.py
git diff --check -- core/platform_clients/base.py core/platform_clients/munpia.py core/platform_clients/novelpia.py ui/publishing.py tests/test_platform_client_base.py tests/test_munpia_client.py tests/test_novelpia_client.py tests/test_publishing_ui.py docs/superpowers/specs/2026-03-16-platform-publish-capability-boundary-v1-design.md docs/superpowers/plans/2026-03-16-platform-publish-capability-boundary-v1.md
```

Expected: clean output

- [ ] **Step 3: Commit the slice**

```bash
git add core/platform_clients/base.py core/platform_clients/munpia.py core/platform_clients/novelpia.py ui/publishing.py tests/test_platform_client_base.py tests/test_munpia_client.py tests/test_novelpia_client.py tests/test_publishing_ui.py docs/superpowers/specs/2026-03-16-platform-publish-capability-boundary-v1-design.md docs/superpowers/plans/2026-03-16-platform-publish-capability-boundary-v1.md
git commit -m "feat: add publish mode capability boundary"
```
