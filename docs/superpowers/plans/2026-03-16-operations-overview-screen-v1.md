# Operations Overview Screen V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class `운영 개요` screen that summarizes project readiness, publishing health, blockers, and next recommended actions without changing existing tabs.

**Architecture:** Introduce a new `ui/operations_dashboard.py` module with pure snapshot/helper functions and a thin Streamlit renderer. Update `ui/app.py` to insert the new screen as the first tab while keeping all existing tabs intact. Reuse existing publishing/workspace helpers instead of inventing new state stores.

**Tech Stack:** Python, Streamlit, unittest, existing UI/publishing/workspace helpers

---

## File Structure

### Create

- `ui/operations_dashboard.py`
  - build snapshot, blockers, and recommendations for the new overview screen
- `tests/test_operations_dashboard.py`
  - overview snapshot/helper coverage

### Modify

- `ui/app.py`
  - add the new first tab and route it to the overview renderer
- `tests/test_ui_helpers.py`
  - assert top-level tab labels include the new overview screen first

## Chunk 1: Red tests first

### Task 1: Add failing tests for the new overview behavior

**Files:**
- Create: `tests/test_operations_dashboard.py`
- Modify: `tests/test_ui_helpers.py`

- [ ] **Step 1: Add failing snapshot/helper tests**

Add tests proving:

- the overview snapshot reports publishing readiness when work ids and credentials are missing
- blocker extraction includes missing platform work mapping and missing credentials
- recommended actions prioritize smoke/configuration work when publishing is not ready

- [ ] **Step 2: Add a failing tab-order test**

Add a test proving `PROJECT_TAB_LABELS` now starts with `운영 개요` and preserves the existing screens after it.

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_operations_dashboard tests.test_ui_helpers -v
```

Expected: FAIL on missing overview module / old tab labels.

## Chunk 2: Minimal implementation

### Task 2: Implement the overview screen

**Files:**
- Create: `ui/operations_dashboard.py`
- Modify: `ui/app.py`

- [ ] **Step 1: Add pure snapshot helpers**

Implement the smallest helpers needed to build:

- top status summary
- publishing readiness summary
- blocker list
- recommended next actions

- [ ] **Step 2: Add the Streamlit renderer**

Render:

- project title/status strip
- four compact status cards
- blocker/warning panel
- next actions list

- [ ] **Step 3: Add the screen as the first tab**

Update `ui/app.py` so the new screen appears first and existing tabs remain available.

- [ ] **Step 4: Run focused tests and make them pass**

Run:

```bash
python3 -m unittest tests.test_operations_dashboard tests.test_ui_helpers -v
```

Expected: PASS

## Chunk 3: Regression and commit

### Task 3: Verify and commit the slice

**Files:**
- Modify: all files above

- [ ] **Step 1: Run a UI-focused regression subset**

Run:

```bash
python3 -m unittest tests.test_operations_dashboard tests.test_ui_helpers tests.test_publishing_ui tests.test_automation_ui tests.test_diagnostics_ui tests.test_context_manager -v
```

Expected: PASS

- [ ] **Step 2: Run syntax and diff verification**

Run:

```bash
python3 -m py_compile ui/operations_dashboard.py ui/app.py tests/test_operations_dashboard.py tests/test_ui_helpers.py
git diff --check -- ui/operations_dashboard.py ui/app.py tests/test_operations_dashboard.py tests/test_ui_helpers.py docs/superpowers/plans/2026-03-16-operations-overview-screen-v1.md
```

Expected: clean output

- [ ] **Step 3: Commit the slice**

```bash
git add ui/operations_dashboard.py ui/app.py tests/test_operations_dashboard.py tests/test_ui_helpers.py docs/superpowers/plans/2026-03-16-operations-overview-screen-v1.md
git commit -m "feat: add operations overview screen"
```
