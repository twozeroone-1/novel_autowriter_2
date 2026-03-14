# Context And Budget Boundary Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route the remaining legacy context update methods through dedicated workspace save boundaries and make the chapters token-budget panel read from the workspace snapshot instead of the full legacy config blob.

**Architecture:** Keep `ContextManager`'s public API stable, but rewire its remaining legacy mutators so they delegate to `save_story_bible_sections(...)`, `save_state(...)`, and `save_previous_summary(...)` rather than rebuilding and saving the whole config dict. In the UI, keep prompt generation behavior unchanged while making budget guidance explicitly consume `get_workspace_settings()` so plot and other legacy-only fields do not leak into the budget boundary.

**Tech Stack:** Python, Streamlit, unittest, existing `ContextManager`, `core/token_budget.py`, `ui/chapters.py`

---

## Chunk 1: ContextManager legacy-write boundary coverage

### Task 1: Add failing tests for the remaining legacy update methods

**Files:**
- Modify: `tests/test_context_manager.py`
- Modify: `core/context.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_update_summary_preserves_story_bible_fields_when_summary_changes():
    ...

def test_apply_context_updates_only_persists_non_empty_overrides():
    ...

def test_update_worldview_preserves_existing_story_bible_sections():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_update_summary_preserves_story_bible_fields_when_summary_changes tests.test_context_manager.TestContextManager.test_apply_context_updates_only_persists_non_empty_overrides tests.test_context_manager.TestContextManager.test_update_worldview_preserves_existing_story_bible_sections -v`
Expected: FAIL because the current legacy methods still save via the full config path.

- [ ] **Step 3: Write the minimal implementation**

In `core/context.py`:

- make `update_summary(...)` compute the updated text and persist it via `save_previous_summary(...)`
- make `apply_context_updates(...)` use `save_state(...)` and `save_previous_summary(...)` only for non-empty overrides, while preserving the existing `backup/applied/current` return shape
- make `update_worldview(...)` reload the current Story Bible-aligned snapshot and persist `worldview` through `save_story_bible_sections(...)` without touching tone/continuity values

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_update_summary_preserves_story_bible_fields_when_summary_changes tests.test_context_manager.TestContextManager.test_apply_context_updates_only_persists_non_empty_overrides tests.test_context_manager.TestContextManager.test_update_worldview_preserves_existing_story_bible_sections -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/context.py tests/test_context_manager.py
git commit -m "feat: align legacy context updates with dedicated save paths"
```

## Chunk 2: Workspace snapshot budget boundary

### Task 2: Add failing tests for budget snapshot reads and implement the UI boundary change

**Files:**
- Modify: `tests/test_ui_helpers.py`
- Modify: `ui/chapters.py`
- Modify: `core/token_budget.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_get_budget_recommendations_ignores_non_workspace_fields():
    ...

def test_render_generation_budget_panel_reads_workspace_snapshot_for_budget_guidance():
    ...
```

The first test should prove that budget guidance only reflects the five workspace fields even if extra config keys are present. The second should use lightweight stubs to prove `render_generation_budget_panel(...)` calls `generator.ctx.get_workspace_settings()` rather than `get_config()`.

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_token_budget tests.test_ui_helpers -v`
Expected: FAIL on the new budget-boundary assertions before implementation.

- [ ] **Step 3: Write the minimal implementation**

In `core/token_budget.py` and `ui/chapters.py`:

- add the smallest normalization helper needed to document the workspace-field boundary, or keep the API as-is if the tests can prove the contract without a rename
- update `render_generation_budget_panel(...)` to read budget stats/recommendations from `generator.ctx.get_workspace_settings()`
- keep `estimate_generation_cost_report(...)` and actual prompt construction unchanged so plot continues to matter only at prompt-build time

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_token_budget tests.test_ui_helpers -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/token_budget.py ui/chapters.py tests/test_token_budget.py tests/test_ui_helpers.py
git commit -m "feat: read budget guidance from workspace snapshot"
```

## Chunk 3: Verification

### Task 3: Run focused and broader regressions

**Files:**
- Test: `tests/test_context_manager.py`
- Test: `tests/test_token_budget.py`
- Test: `tests/test_ui_helpers.py`

- [ ] **Step 1: Run focused context and UI tests**

Run: `python3 -m unittest tests.test_context_manager tests.test_token_budget tests.test_ui_helpers -v`
Expected: PASS

- [ ] **Step 2: Run broader origin-pipeline regressions**

Run: `python3 -m unittest tests.test_story_bible_store tests.test_canon_store tests.test_release_policy_store tests.test_episode_artifact_store tests.test_run_snapshot_store tests.test_origin_quality tests.test_context_manager tests.test_generator_storage tests.test_chapter_source tests.test_automation_store tests.test_automation_runtime tests.test_automation_ui tests.test_diagnostics_ui tests.test_automator tests.test_canon_extractor tests.test_publishing_executor tests.test_publishing_runtime tests.test_token_budget tests.test_ui_helpers -v`
Expected: PASS

- [ ] **Step 3: Run syntax verification**

Run: `python3 -m py_compile core/context.py core/token_budget.py ui/chapters.py tests/test_context_manager.py tests/test_token_budget.py tests/test_ui_helpers.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-03-14-context-and-budget-boundary.md
git commit -m "docs: add context and budget boundary plan"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-14-context-and-budget-boundary.md`. Ready to execute?
