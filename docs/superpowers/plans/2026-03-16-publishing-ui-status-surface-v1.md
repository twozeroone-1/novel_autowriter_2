# Publishing UI Status Surface V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make scheduled publishing visible in the existing publishing UI without redesigning the tab.

**Architecture:** Keep the current publishing tab structure and update only the helper/formatting boundaries. `ui/publishing.py` should treat `scheduled` as a first-class runtime, queue, and history state, while `tests/test_publishing_ui.py` locks the operator-facing semantics in place.

**Tech Stack:** Python, unittest, existing Streamlit publishing tab helpers

---

## File Structure

### Modified files

- `ui/publishing.py`
  - add scheduled-aware runtime, queue-count, and history formatting
- `tests/test_publishing_ui.py`
  - add focused red/green tests for scheduled UI behavior

## Chunk 1: Add failing UI tests

### Task 1: Write the red tests

**Files:**
- Modify: `tests/test_publishing_ui.py`

- [ ] **Step 1: Add a failing runtime status test for scheduled**

Add a test proving:

- `format_publishing_runtime_status({"status": "scheduled"}) == "예약 대기"`

- [ ] **Step 2: Add failing queue/history tests for scheduled**

Add tests proving:

- `count_pending_publishing_jobs(...)` includes scheduled jobs
- `build_publishing_queue_rows(...)` preserves scheduled status rows
- `build_publishing_history_rows(...)` renders `예약` when any platform result is `scheduled`

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_publishing_ui -v
```

Expected: FAIL on missing scheduled UI behavior.

## Chunk 2: Implement minimal scheduled-aware UI helpers

### Task 2: Make the tests pass with the smallest helper changes

**Files:**
- Modify: `ui/publishing.py`
- Modify: `tests/test_publishing_ui.py`

- [ ] **Step 1: Add scheduled runtime formatting**

Implement the smallest change so `format_publishing_runtime_status(...)` returns `예약 대기` for scheduled runtime.

- [ ] **Step 2: Count scheduled jobs as active queued work**

Implement the smallest change so `count_pending_publishing_jobs(...)` counts `scheduled` along with pending and partial-failed jobs.

- [ ] **Step 3: Add scheduled-aware history result labeling**

Implement the smallest change so history rows show `예약` when top-level success is false but at least one platform result is `scheduled`.

- [ ] **Step 4: Run focused tests and make them pass**

Run:

```bash
python3 -m unittest tests.test_publishing_ui -v
```

Expected: PASS

## Chunk 3: Verify and commit

### Task 3: Full slice verification

**Files:**
- Modify: all files above

- [ ] **Step 1: Run the established publishing regression subset**

Run:

```bash
python3 -m unittest tests.test_publishing_ui tests.test_publishing_runtime tests.test_publishing_policy tests.test_publishing_executor tests.test_publishing_incidents tests.test_novelpia_client -v
```

Expected: PASS

- [ ] **Step 2: Run syntax and diff verification**

Run:

```bash
python3 -m py_compile ui/publishing.py tests/test_publishing_ui.py
git diff --check -- ui/publishing.py tests/test_publishing_ui.py docs/superpowers/specs/2026-03-16-publishing-ui-status-surface-v1-design.md docs/superpowers/plans/2026-03-16-publishing-ui-status-surface-v1.md
```

Expected: clean output

- [ ] **Step 3: Commit the slice**

```bash
git add ui/publishing.py tests/test_publishing_ui.py docs/superpowers/specs/2026-03-16-publishing-ui-status-surface-v1-design.md docs/superpowers/plans/2026-03-16-publishing-ui-status-surface-v1.md
git commit -m "feat: surface scheduled publishing state in ui"
```
