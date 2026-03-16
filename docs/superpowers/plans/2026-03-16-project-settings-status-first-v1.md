# Project Settings Status-First V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework `[1] 프로젝트 통합 설정` into a status-first hub that shows readiness, warnings, and next actions before the existing editors.

**Architecture:** Keep `ui/workspace.py` as the single rendering boundary for this slice, but add small snapshot helpers so the status-first summary is computed separately from the raw editor sections. Reuse existing `field_stats`, `ProjectFieldPanel`, canon/release summaries, and the current `PREVIOUS SUMMARY` editor without changing persistence behavior.

**Tech Stack:** Python, Streamlit, unittest

---

## Chunk 1: Status Snapshot Helpers

### Task 1: Add failing tests for project settings status snapshot

**Files:**
- Modify: `tests/test_ui_helpers.py`
- Modify: `ui/workspace.py`

- [ ] **Step 1: Write failing tests**

Add tests for:
- a snapshot helper that reports filled core document count and attention count
- a helper that reports `PREVIOUS SUMMARY` status as `empty`, `editing`, or `saved`
- a helper that generates warnings / recommended actions from missing or oversized documents

- [ ] **Step 2: Run targeted tests to verify failure**

Run: `python3 -m unittest tests.test_ui_helpers -v`

Expected: FAIL because the new helpers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

In `ui/workspace.py`, add focused helpers for:
- core document readiness snapshot
- previous summary status snapshot
- warning / recommended action list construction

- [ ] **Step 4: Re-run targeted tests**

Run: `python3 -m unittest tests.test_ui_helpers -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/workspace.py tests/test_ui_helpers.py
git commit -m "test: add project settings status snapshot helpers"
```

## Chunk 2: Status-First Layout

### Task 2: Reorder the project settings screen around status

**Files:**
- Modify: `ui/workspace.py`
- Test: `tests/test_ui_helpers.py`

- [ ] **Step 1: Write failing layout tests**

Add tests that lock:
- status summary renders before editor sections
- warning / next-action sections render when needed
- the existing `PREVIOUS SUMMARY`, structured store overview, character management, and diagnostics panel remain in the render flow

- [ ] **Step 2: Run focused tests to verify failure**

Run: `python3 -m unittest tests.test_ui_helpers -v`

Expected: FAIL because the new layout structure is not rendered yet.

- [ ] **Step 3: Implement minimal layout change**

Update `render_project_settings_tab(...)` to:
- render status metrics and summary cards first
- render warning / next-action sections next
- wrap core document editors under a `고급 편집` section
- keep `PREVIOUS SUMMARY` in place after that
- leave lower helper panels intact

- [ ] **Step 4: Re-run focused tests**

Run: `python3 -m unittest tests.test_ui_helpers -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/workspace.py tests/test_ui_helpers.py
git commit -m "feat: add status-first project settings screen"
```

## Chunk 3: UI Regression Verification

### Task 3: Run workspace-centric UI regression

**Files:**
- Modify: `tests/test_operations_dashboard.py` (only if needed)
- Modify: `tests/test_episode_workflow.py` (only if needed)
- Modify: `tests/test_publishing_ui.py` (only if needed)

- [ ] **Step 1: Run curated UI regression**

Run:

```bash
python3 -m unittest \
  tests.test_ui_helpers \
  tests.test_operations_dashboard \
  tests.test_episode_workflow \
  tests.test_publishing_ui \
  tests.test_automation_ui \
  tests.test_diagnostics_ui \
  tests.test_context_manager -v
```

Expected: PASS

- [ ] **Step 2: Run py_compile**

Run:

```bash
python3 -m py_compile \
  ui/workspace.py \
  tests/test_ui_helpers.py
```

Expected: no output

- [ ] **Step 3: Run diff check**

Run:

```bash
git diff --check -- ui/workspace.py tests/test_ui_helpers.py docs/superpowers/plans/2026-03-16-project-settings-status-first-v1.md
```

Expected: no output

- [ ] **Step 4: Commit final polish**

```bash
git add ui/workspace.py tests/test_ui_helpers.py docs/superpowers/plans/2026-03-16-project-settings-status-first-v1.md
git commit -m "test: verify project settings status-first regression"
```
