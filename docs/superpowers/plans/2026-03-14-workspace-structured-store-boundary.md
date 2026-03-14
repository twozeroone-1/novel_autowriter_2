# Workspace Structured Store Boundary Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the workspace settings tab save Story Bible fields through the structured store boundary, split state/summary saves, and surface Canon/Release Policy as read-only structured-store summaries.

**Architecture:** Add narrow workspace-specific load/save helpers to `ContextManager`, switch `ui/workspace.py` to those helpers instead of bulk `save_config()`, and add small read-only summary helpers for `CanonStore` and `ReleasePolicyStore` without changing other tabs yet.

**Tech Stack:** Python, Streamlit, unittest, existing `ContextManager`, `StoryBibleStore`, `CanonStore`, `ReleasePolicyStore`

---

## Chunk 1: ContextManager workspace boundary

### Task 1: Add workspace-specific load/save helpers

**Files:**
- Modify: `core/context.py`
- Modify: `tests/test_context_manager.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_get_workspace_settings_reads_story_bible_and_legacy_state_fields():
    ...

def test_save_story_bible_sections_updates_story_bible_store_and_legacy_config():
    ...

def test_save_state_and_previous_summary_update_only_target_fields():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_context_manager -v`
Expected: FAIL because the new workspace boundary helpers do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

In `core/context.py`:

- add `get_workspace_settings()`
- add `save_story_bible_sections(...)`
- add `save_state(...)`
- add `save_previous_summary(...)`
- keep `save_config()` for compatibility, but reuse the new helpers where sensible

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_context_manager -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/context.py tests/test_context_manager.py
git commit -m "feat: add workspace-specific context boundaries"
```

## Chunk 2: Workspace helper coverage

### Task 2: Add helper-level tests for structured-store summaries

**Files:**
- Modify: `ui/workspace.py`
- Modify: `tests/test_ui_helpers.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_build_canon_store_summary_counts_structured_sections():
    ...

def test_build_release_policy_summary_lists_enabled_platforms():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_ui_helpers -v`
Expected: FAIL because the structured-store summary helpers do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

In `ui/workspace.py`:

- add a small helper/dataclass for Canon summary
- add a small helper/dataclass for Release Policy summary
- keep them pure so they can be tested without Streamlit rendering

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_ui_helpers -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/workspace.py tests/test_ui_helpers.py
git commit -m "feat: add structured store summaries for workspace"
```

## Chunk 3: Workspace tab integration

### Task 3: Switch the workspace tab to the new boundaries

**Files:**
- Modify: `ui/workspace.py`
- Modify: `ui/app.py`
- Modify: `tests/test_ui_helpers.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_load_project_textareas_accepts_workspace_settings_snapshot():
    ...
```

If needed, add pure helper tests for save routing decisions instead of Streamlit render tests.

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_ui_helpers -v`
Expected: FAIL because the UI helpers still assume the old config-only workflow.

- [ ] **Step 3: Write the minimal implementation**

In `ui/workspace.py`:

- use `generator.ctx.get_workspace_settings()` for the project settings tab
- route Story Bible button saves and the main save button through `save_story_bible_sections(...)`
- route state save through `save_state(...)`
- route previous summary save through `save_previous_summary(...)`
- render read-only Canon / Release Policy summaries in an expander

In `ui/app.py`:

- load textarea defaults from `get_workspace_settings()` on project switch

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_ui_helpers -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/workspace.py ui/app.py tests/test_ui_helpers.py
git commit -m "feat: route workspace settings through structured stores"
```

## Chunk 4: Verification

### Task 4: Run focused and broader regressions

**Files:**
- Test: `tests/test_context_manager.py`
- Test: `tests/test_ui_helpers.py`
- Test: `ui/app.py`
- Test: `ui/workspace.py`

- [ ] **Step 1: Run focused workspace tests**

Run: `python3 -m unittest tests.test_context_manager tests.test_ui_helpers -v`
Expected: PASS

- [ ] **Step 2: Run broader origin-pipeline regressions**

Run: `python3 -m unittest tests.test_story_bible_store tests.test_canon_store tests.test_release_policy_store tests.test_episode_artifact_store tests.test_run_snapshot_store tests.test_origin_quality tests.test_context_manager tests.test_generator_storage tests.test_chapter_source tests.test_automation_store tests.test_automation_runtime tests.test_automation_ui tests.test_diagnostics_ui tests.test_automator tests.test_canon_extractor tests.test_publishing_executor tests.test_publishing_runtime tests.test_ui_helpers -v`
Expected: PASS

- [ ] **Step 3: Run syntax verification**

Run: `python3 -m py_compile core/context.py ui/workspace.py ui/app.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-03-14-workspace-structured-store-boundary-design.md docs/superpowers/plans/2026-03-14-workspace-structured-store-boundary.md
git commit -m "docs: add workspace structured store boundary plan"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-14-workspace-structured-store-boundary.md`. Ready to execute?
