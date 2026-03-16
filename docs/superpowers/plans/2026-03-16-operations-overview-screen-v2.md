# Operations Overview Screen V2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a workflow timeline and structured shortcut actions to the `운영 개요` screen so the first screen clearly shows current episode phase and next destination.

**Architecture:** Extend the dashboard snapshot model with lightweight timeline inference and shortcut labels, then render those two sections below the existing blockers/actions area. Reuse current publishing and workspace signals rather than creating a new runtime model.

**Tech Stack:** Python, Streamlit, unittest

---

## Chunk 1: Dashboard Snapshot Tests

### Task 1: Add failing tests for timeline and shortcuts

**Files:**
- Modify: `/mnt/c/Users/W/novel_autowriter_2/tests/test_operations_dashboard.py`
- Test: `/mnt/c/Users/W/novel_autowriter_2/tests/test_operations_dashboard.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

- healthy timeline progression
- blocked timeline progression
- shortcut action labels

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_operations_dashboard -v
```

Expected: FAIL because the new snapshot fields do not exist yet.

## Chunk 2: Snapshot Logic

### Task 2: Implement timeline and shortcut inference

**Files:**
- Modify: `/mnt/c/Users/W/novel_autowriter_2/ui/operations_dashboard.py`
- Test: `/mnt/c/Users/W/novel_autowriter_2/tests/test_operations_dashboard.py`

- [ ] **Step 1: Add context loaders/helpers**

Load enough context to infer:

- plan presence
- latest episode presence
- latest quality status
- publish/reconciliation state

- [ ] **Step 2: Extend `build_operations_overview_snapshot(...)`**

Return:

- `timeline_steps`
- `shortcut_actions`

- [ ] **Step 3: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_operations_dashboard -v
```

Expected: PASS

## Chunk 3: Dashboard Rendering

### Task 3: Render timeline and shortcuts

**Files:**
- Modify: `/mnt/c/Users/W/novel_autowriter_2/ui/operations_dashboard.py`
- Test: `/mnt/c/Users/W/novel_autowriter_2/tests/test_operations_dashboard.py`

- [ ] **Step 1: Render timeline section**

Keep rendering simple: a row of columns with stage label + state.

- [ ] **Step 2: Render shortcut actions**

Render a structured list below the timeline.

- [ ] **Step 3: Run UI-adjacent regression**

Run:

```bash
python3 -m unittest tests.test_operations_dashboard tests.test_episode_workflow tests.test_publishing_ui tests.test_ui_helpers -v
```

Expected: PASS

## Chunk 4: Verification

### Task 4: Final verification and commit readiness

**Files:**
- Modify: `/mnt/c/Users/W/novel_autowriter_2/ui/operations_dashboard.py`
- Modify: `/mnt/c/Users/W/novel_autowriter_2/tests/test_operations_dashboard.py`

- [ ] **Step 1: Run compile check**

Run:

```bash
python3 -m py_compile ui/operations_dashboard.py tests/test_operations_dashboard.py
```

Expected: no output

- [ ] **Step 2: Run diff check**

Run:

```bash
git diff --check -- ui/operations_dashboard.py tests/test_operations_dashboard.py docs/superpowers/specs/2026-03-16-operations-overview-screen-v2-design.md docs/superpowers/plans/2026-03-16-operations-overview-screen-v2.md
```

Expected: no output

- [ ] **Step 3: Commit**

```bash
git add ui/operations_dashboard.py tests/test_operations_dashboard.py docs/superpowers/specs/2026-03-16-operations-overview-screen-v2-design.md docs/superpowers/plans/2026-03-16-operations-overview-screen-v2.md
git commit -m "feat: add operations overview timeline"
```
