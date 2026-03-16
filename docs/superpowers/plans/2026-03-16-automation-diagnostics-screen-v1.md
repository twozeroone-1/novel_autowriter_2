# Automation Diagnostics Screen V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the automation screen into a readiness-first `자동화/진단` surface that shows schedule health, runtime state, queue pressure, and recent diagnostics before raw configuration forms.

**Architecture:** Keep `ui/automation.py` as the main automation tab renderer, but add pure snapshot helpers that summarize automation runtime and diagnostics state together. Reuse `ui.diagnostics` helper functions for compact diagnostics metadata, then move the existing queue/settings/history controls below the new operator summary as advanced controls.

**Tech Stack:** Python, Streamlit, unittest, existing automation store/runtime, diagnostics helpers

---

## File Structure

### Modify

- `ui/automation.py`
  - add pure automation/diagnostics readiness helper functions
  - reorder rendering into status-first sections
- `ui/diagnostics.py`
  - add compact diagnostics snapshot helpers reusable outside the settings expander
- `ui/app.py`
  - rename the automation tab label to `자동화/진단`
- `tests/test_automation_ui.py`
  - add readiness snapshot coverage
- `tests/test_diagnostics_ui.py`
  - add compact diagnostics summary coverage
- `tests/test_ui_helpers.py`
  - update tab-order expectations

### Create

- none

## Chunk 1: Red tests first

### Task 1: Add failing readiness and label tests

**Files:**
- Modify: `tests/test_automation_ui.py`
- Modify: `tests/test_diagnostics_ui.py`
- Modify: `tests/test_ui_helpers.py`

- [ ] **Step 1: Add failing automation snapshot tests**

Lock at least:

- automation snapshot surfaces schedule/runtime/pending counts
- blockers mention paused or missing queue readiness before raw forms
- next actions prioritize queue work or schedule/runtime intervention

- [ ] **Step 2: Add failing diagnostics summary tests**

Lock at least:

- compact diagnostics snapshot exposes run count/failure count/latest backend
- diagnostics alert state marks recent failures as warning

- [ ] **Step 3: Add failing tab label expectation**

Update `PROJECT_TAB_LABELS` expectation so the automation tab label becomes `자동화/진단`.

- [ ] **Step 4: Run focused tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_automation_ui tests.test_diagnostics_ui tests.test_ui_helpers -v
```

Expected: FAIL on missing helper symbols / old automation tab label.

## Chunk 2: Minimal implementation

### Task 2: Rework the automation screen

**Files:**
- Modify: `ui/automation.py`
- Modify: `ui/diagnostics.py`
- Modify: `ui/app.py`

- [ ] **Step 1: Add compact diagnostics snapshot helpers**

Implement minimal helpers in `ui/diagnostics.py` for:

- latest diagnostics compact summary text
- diagnostics status level (`healthy` / `warning` / `empty`)
- recommended diagnostics action text

- [ ] **Step 2: Add automation operations snapshot helpers**

Implement minimal helpers in `ui/automation.py` for:

- automation/diagnostics summary snapshot
- blockers list
- next recommended actions

- [ ] **Step 3: Reorder the renderer**

Update `render_automation_tab()` to show:

- header and summary metrics
- automation runtime / diagnostics readiness summary
- blockers and next-action section
- recent queue/history preview
- advanced settings/forms after the status-first sections

- [ ] **Step 4: Rename the tab label**

Update `ui/app.py` so the top-level navigation says `자동화/진단`.

- [ ] **Step 5: Run focused tests and make them pass**

Run:

```bash
python3 -m unittest tests.test_automation_ui tests.test_diagnostics_ui tests.test_ui_helpers -v
```

Expected: PASS

## Chunk 3: Regression and commit

### Task 3: Verify and commit the slice

**Files:**
- Modify: all files above

- [ ] **Step 1: Run a UI-focused regression subset**

Run:

```bash
python3 -m unittest tests.test_automation_ui tests.test_diagnostics_ui tests.test_ui_helpers tests.test_operations_dashboard tests.test_episode_workflow tests.test_publishing_ui tests.test_context_manager -v
```

Expected: PASS

- [ ] **Step 2: Run syntax and diff verification**

Run:

```bash
python3 -m py_compile ui/automation.py ui/diagnostics.py ui/app.py tests/test_automation_ui.py tests/test_diagnostics_ui.py tests/test_ui_helpers.py
git diff --check -- ui/automation.py ui/diagnostics.py ui/app.py tests/test_automation_ui.py tests/test_diagnostics_ui.py tests/test_ui_helpers.py docs/superpowers/plans/2026-03-16-automation-diagnostics-screen-v1.md
```

Expected: clean output

- [ ] **Step 3: Commit the slice**

```bash
git add ui/automation.py ui/diagnostics.py ui/app.py tests/test_automation_ui.py tests/test_diagnostics_ui.py tests/test_ui_helpers.py docs/superpowers/plans/2026-03-16-automation-diagnostics-screen-v1.md
git commit -m "feat: add automation diagnostics screen"
```
