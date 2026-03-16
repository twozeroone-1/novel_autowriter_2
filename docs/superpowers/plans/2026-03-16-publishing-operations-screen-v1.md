# Publishing Operations Screen V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the publishing screen into a readiness-first `발행 운영` surface that shows platform health, queue, and runtime status before raw settings forms.

**Architecture:** Keep `ui/publishing.py` as the single publishing UI module, but add pure readiness snapshot helpers that can be tested independently. Reorder `render_publishing_tab()` so operators see platform cards, queue summary, and runtime/history summary first, while existing settings forms remain below as advanced configuration.

**Tech Stack:** Python, Streamlit, unittest, existing publishing store/helpers

---

## File Structure

### Modify

- `ui/publishing.py`
  - add pure readiness helper functions
  - reorganize rendering order and labels
- `ui/app.py`
  - rename the top-level tab label to `발행 운영`
- `tests/test_publishing_ui.py`
  - add readiness helper coverage
- `tests/test_ui_helpers.py`
  - update tab-order expectations

### Create

- none

## Chunk 1: Red tests first

### Task 1: Add failing readiness and tab-label tests

**Files:**
- Modify: `tests/test_publishing_ui.py`
- Modify: `tests/test_ui_helpers.py`

- [ ] **Step 1: Add failing readiness snapshot tests**

Lock at least:

- enabled platform with missing credentials/work mapping is marked not ready
- ready platform row reports credential/work/upload-url readiness
- next action text prioritizes smoke/configuration when runtime is otherwise idle

- [ ] **Step 2: Add a failing tab-label test**

Update `PROJECT_TAB_LABELS` expectation so the final tab label is `발행 운영`.

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_publishing_ui tests.test_ui_helpers -v
```

Expected: FAIL on missing helper symbols / old tab label.

## Chunk 2: Minimal implementation

### Task 2: Rework the publishing screen

**Files:**
- Modify: `ui/publishing.py`
- Modify: `ui/app.py`

- [ ] **Step 1: Add pure readiness helper functions**

Implement minimal helpers for:

- per-platform readiness rows
- publishing operations snapshot
- next recommended actions

- [ ] **Step 2: Reorder the renderer**

Update `render_publishing_tab()` to show:

- header and summary metrics
- platform readiness cards
- queue summary preview
- runtime/history summary preview
- advanced settings/forms after the status-first sections

- [ ] **Step 3: Rename the tab label**

Update `ui/app.py` so the top-level navigation says `발행 운영`.

- [ ] **Step 4: Run focused tests and make them pass**

Run:

```bash
python3 -m unittest tests.test_publishing_ui tests.test_ui_helpers -v
```

Expected: PASS

## Chunk 3: Regression and commit

### Task 3: Verify and commit the slice

**Files:**
- Modify: all files above

- [ ] **Step 1: Run a UI-focused regression subset**

Run:

```bash
python3 -m unittest tests.test_publishing_ui tests.test_ui_helpers tests.test_operations_dashboard tests.test_episode_workflow tests.test_automation_ui tests.test_diagnostics_ui tests.test_context_manager -v
```

Expected: PASS

- [ ] **Step 2: Run syntax and diff verification**

Run:

```bash
python3 -m py_compile ui/publishing.py ui/app.py tests/test_publishing_ui.py tests/test_ui_helpers.py
git diff --check -- ui/publishing.py ui/app.py tests/test_publishing_ui.py tests/test_ui_helpers.py docs/superpowers/plans/2026-03-16-publishing-operations-screen-v1.md
```

Expected: clean output

- [ ] **Step 3: Commit the slice**

```bash
git add ui/publishing.py ui/app.py tests/test_publishing_ui.py tests/test_ui_helpers.py docs/superpowers/plans/2026-03-16-publishing-operations-screen-v1.md
git commit -m "feat: add publishing operations screen"
```
