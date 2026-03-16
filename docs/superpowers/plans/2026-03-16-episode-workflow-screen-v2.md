# Episode Workflow Screen V2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen the `회차 워크플로` tab so operators can see latest draft content, quality gate details, and publish queue linkage without jumping across multiple tabs.

**Architecture:** Keep the current workflow screen layout and enrich the snapshot model behind it. Add data extraction helpers inside `ui/episode_workflow.py`, then render richer status summaries and previews while leaving legacy tabs intact.

**Tech Stack:** Python, Streamlit, unittest

---

## Chunk 1: Workflow Snapshot Tests

### Task 1: Add failing workflow tests

**Files:**
- Modify: `/mnt/c/Users/W/novel_autowriter_2/tests/test_episode_workflow.py`
- Test: `/mnt/c/Users/W/novel_autowriter_2/tests/test_episode_workflow.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

- latest draft excerpt/path exposure
- critic/repair/regenerate detail fields
- queue linkage for latest episode

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_episode_workflow -v
```

Expected: FAIL because the new snapshot keys and behavior do not exist yet.

## Chunk 2: Workflow Snapshot Implementation

### Task 2: Implement richer workflow snapshot logic

**Files:**
- Modify: `/mnt/c/Users/W/novel_autowriter_2/ui/episode_workflow.py`
- Test: `/mnt/c/Users/W/novel_autowriter_2/tests/test_episode_workflow.py`

- [ ] **Step 1: Add minimal helpers**

Add helpers for:

- reading latest episode markdown preview
- extracting critic status and repair/regenerate booleans
- inferring queue linkage from pending/scheduled jobs

- [ ] **Step 2: Update `build_episode_workflow_snapshot(...)`**

Return:

- `draft_preview`
- `draft_path`
- `critic_status`
- `repair_applied`
- `regenerate_applied`
- `queue_linked`
- `queue_link_summary`

- [ ] **Step 3: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_episode_workflow -v
```

Expected: PASS

## Chunk 3: Workflow Screen Rendering

### Task 3: Surface richer workflow details in the UI

**Files:**
- Modify: `/mnt/c/Users/W/novel_autowriter_2/ui/episode_workflow.py`
- Test: `/mnt/c/Users/W/novel_autowriter_2/tests/test_episode_workflow.py`

- [ ] **Step 1: Render enriched summary/detail blocks**

Add visible sections for:

- latest draft preview
- quality gate detail
- publishing linkage detail

- [ ] **Step 2: Keep layout stable**

Do not add new tabs or navigation changes. Keep the current left/right split and step row.

- [ ] **Step 3: Run broader UI-adjacent regression**

Run:

```bash
python3 -m unittest tests.test_episode_workflow tests.test_operations_dashboard tests.test_publishing_ui tests.test_ui_helpers -v
```

Expected: PASS

## Chunk 4: Verification

### Task 4: Final verification and commit readiness

**Files:**
- Modify: `/mnt/c/Users/W/novel_autowriter_2/ui/episode_workflow.py`
- Modify: `/mnt/c/Users/W/novel_autowriter_2/tests/test_episode_workflow.py`

- [ ] **Step 1: Run compile check**

Run:

```bash
python3 -m py_compile ui/episode_workflow.py tests/test_episode_workflow.py
```

Expected: no output

- [ ] **Step 2: Run diff cleanliness check**

Run:

```bash
git diff --check -- ui/episode_workflow.py tests/test_episode_workflow.py docs/superpowers/specs/2026-03-16-episode-workflow-screen-v2-design.md docs/superpowers/plans/2026-03-16-episode-workflow-screen-v2.md
```

Expected: no output

- [ ] **Step 3: Commit**

```bash
git add ui/episode_workflow.py tests/test_episode_workflow.py docs/superpowers/specs/2026-03-16-episode-workflow-screen-v2-design.md docs/superpowers/plans/2026-03-16-episode-workflow-screen-v2.md
git commit -m "feat: strengthen episode workflow screen"
```
