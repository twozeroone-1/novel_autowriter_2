# Episode Workflow Shortcuts V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Demote legacy episode task tabs in the top navigation and add structured shortcut actions inside the workflow screen.

**Architecture:** Keep the existing tab shell and generators/reviewers untouched. Change only labels and workflow snapshot/rendering so the workflow tab becomes the primary decision surface and legacy tabs become explicitly advanced tools.

**Tech Stack:** Python, Streamlit, unittest

---

## Chunk 1: Tests

### Task 1: Add failing tests for tab labels and workflow shortcuts

**Files:**
- Modify: `/mnt/c/Users/W/novel_autowriter_2/tests/test_ui_helpers.py`
- Modify: `/mnt/c/Users/W/novel_autowriter_2/tests/test_episode_workflow.py`

- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_ui_helpers tests.test_episode_workflow -v
```

Expected: FAIL because the new labels and shortcut structures do not exist yet.

## Chunk 2: Implementation

### Task 2: Rename top-level tab labels

**Files:**
- Modify: `/mnt/c/Users/W/novel_autowriter_2/ui/app.py`
- Test: `/mnt/c/Users/W/novel_autowriter_2/tests/test_ui_helpers.py`

- [ ] **Step 1: Update `PROJECT_TAB_LABELS`**
- [ ] **Step 2: Run relevant tests**

### Task 3: Add workflow shortcut actions

**Files:**
- Modify: `/mnt/c/Users/W/novel_autowriter_2/ui/episode_workflow.py`
- Test: `/mnt/c/Users/W/novel_autowriter_2/tests/test_episode_workflow.py`

- [ ] **Step 1: Extend workflow snapshot with structured shortcuts**
- [ ] **Step 2: Render shortcut actions in the workflow screen**
- [ ] **Step 3: Run relevant tests**

## Chunk 3: Verification

### Task 4: Verify and prepare commit

**Files:**
- Modify: `/mnt/c/Users/W/novel_autowriter_2/ui/app.py`
- Modify: `/mnt/c/Users/W/novel_autowriter_2/ui/episode_workflow.py`
- Modify: `/mnt/c/Users/W/novel_autowriter_2/tests/test_ui_helpers.py`
- Modify: `/mnt/c/Users/W/novel_autowriter_2/tests/test_episode_workflow.py`

- [ ] **Step 1: Run UI regression**

```bash
python3 -m unittest tests.test_ui_helpers tests.test_episode_workflow tests.test_operations_dashboard tests.test_publishing_ui -v
```

- [ ] **Step 2: Run compile and diff checks**

```bash
python3 -m py_compile ui/app.py ui/episode_workflow.py tests/test_ui_helpers.py tests/test_episode_workflow.py
git diff --check -- ui/app.py ui/episode_workflow.py tests/test_ui_helpers.py tests/test_episode_workflow.py docs/superpowers/specs/2026-03-16-episode-workflow-shortcuts-v1-design.md docs/superpowers/plans/2026-03-16-episode-workflow-shortcuts-v1.md
```

- [ ] **Step 3: Commit**

```bash
git add ui/app.py ui/episode_workflow.py tests/test_ui_helpers.py tests/test_episode_workflow.py docs/superpowers/specs/2026-03-16-episode-workflow-shortcuts-v1-design.md docs/superpowers/plans/2026-03-16-episode-workflow-shortcuts-v1.md
git commit -m "feat: center workflow shortcuts in UI"
```
