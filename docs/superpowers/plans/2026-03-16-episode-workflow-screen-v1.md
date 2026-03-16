# Episode Workflow Screen V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `회차 워크플로` screen that shows the recent episode pipeline across planning, draft creation, quality gate, and publish packaging in one place.

**Architecture:** Introduce a new `ui/episode_workflow.py` module with pure snapshot builders plus a thin Streamlit renderer. Keep the existing generation/review/publishing tabs intact and add the new screen as a dashboard layer over existing artifacts, run snapshots, queue state, and history.

**Tech Stack:** Python, Streamlit, unittest, existing generator/publishing stores

---

## File Structure

### Create

- `ui/episode_workflow.py`
  - load recent workflow inputs from artifacts and run snapshots
  - build a pure workflow snapshot for rendering
- `tests/test_episode_workflow.py`
  - workflow snapshot coverage

### Modify

- `ui/app.py`
  - insert the new `회차 워크플로` tab after `운영 개요`
- `tests/test_ui_helpers.py`
  - assert top-level tab labels include the new workflow tab in the expected position

## Chunk 1: Red tests first

### Task 1: Add failing workflow snapshot and tab-order tests

**Files:**
- Create: `tests/test_episode_workflow.py`
- Modify: `tests/test_ui_helpers.py`

- [ ] **Step 1: Add failing workflow snapshot tests**

Lock at least:

- latest manifest episode becomes the displayed draft summary
- publishable quality + package output marks the later steps complete
- hard-fail quality blocks the workflow and recommends fixing quality first

- [ ] **Step 2: Add a failing tab-order test**

Update the top-level tab order assertion so it expects:

- `운영 개요`
- `회차 워크플로`
- existing tabs after that

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_episode_workflow tests.test_ui_helpers -v
```

Expected: FAIL on missing workflow module / old tab labels.

## Chunk 2: Minimal implementation

### Task 2: Implement the workflow screen

**Files:**
- Create: `ui/episode_workflow.py`
- Modify: `ui/app.py`

- [ ] **Step 1: Add artifact/run snapshot loaders**

Implement minimal helpers to read:

- latest episode from `EpisodeArtifactStore.manifest`
- latest chapter planner snapshot from `runs/chapter_*/episode_plan.json`
- latest publish quality snapshot from `runs/origin_*/quality_report.json`
- latest packager snapshot from `runs/origin_*/packager_report.json`
- queue/history summaries from `PublishingStore`

- [ ] **Step 2: Add pure workflow snapshot logic**

Build a snapshot that includes:

- recent episode headline
- four workflow step states
- left-column summary bullets
- right-column detail payloads
- next recommended actions

- [ ] **Step 3: Add the Streamlit renderer**

Render:

- workflow header and caption
- four step cards
- current workflow summary
- detail previews for plan / quality / packager
- next actions

- [ ] **Step 4: Wire the new tab into `ui/app.py`**

Insert `회차 워크플로` after `운영 개요` while preserving all existing tabs.

- [ ] **Step 5: Run focused tests and make them pass**

Run:

```bash
python3 -m unittest tests.test_episode_workflow tests.test_ui_helpers -v
```

Expected: PASS

## Chunk 3: Regression and commit

### Task 3: Verify and commit the slice

**Files:**
- Modify: all files above

- [ ] **Step 1: Run a UI-focused regression subset**

Run:

```bash
python3 -m unittest tests.test_episode_workflow tests.test_ui_helpers tests.test_operations_dashboard tests.test_publishing_ui tests.test_automation_ui tests.test_diagnostics_ui tests.test_context_manager -v
```

Expected: PASS

- [ ] **Step 2: Run syntax and diff verification**

Run:

```bash
python3 -m py_compile ui/episode_workflow.py ui/app.py tests/test_episode_workflow.py tests/test_ui_helpers.py
git diff --check -- ui/episode_workflow.py ui/app.py tests/test_episode_workflow.py tests/test_ui_helpers.py docs/superpowers/plans/2026-03-16-episode-workflow-screen-v1.md
```

Expected: clean output

- [ ] **Step 3: Commit the slice**

```bash
git add ui/episode_workflow.py ui/app.py tests/test_episode_workflow.py tests/test_ui_helpers.py docs/superpowers/plans/2026-03-16-episode-workflow-screen-v1.md
git commit -m "feat: add episode workflow screen"
```
