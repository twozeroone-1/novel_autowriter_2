# Context Reader Detachment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewire `ContextManager`'s internal prompt/context readers so they no longer depend on `get_config()` as their primary read path.

**Architecture:** Keep the public reader methods unchanged, but introduce small internal helpers for Story Bible fields and state/summary fields. These helpers read directly from the structured stores or the minimal legacy-backed state snapshot, allowing `get_worldview_context()`, `get_continuity_context()`, `get_state_context()`, and `build_updated_summary_text()` to stop routing through the merged legacy config snapshot.

**Tech Stack:** Python, unittest, existing `ContextManager`, `StoryBibleStore`, legacy state config snapshot, plot API unchanged

---

## Chunk 1: Reader detachment tests

### Task 1: Add failing tests that prove prompt readers no longer use `get_config()`

**Files:**
- Modify: `tests/test_context_manager.py`
- Modify: `core/context.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_get_worldview_context_reads_story_bible_without_get_config():
    ...

def test_get_continuity_context_reads_story_bible_without_get_config():
    ...

def test_get_state_context_reads_state_snapshot_without_get_config():
    ...

def test_build_updated_summary_text_reads_existing_summary_without_get_config():
    ...
```

Each test should patch `manager.get_config` to raise `AssertionError("get_config should not be used")` after seeding data through the dedicated save paths.

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_get_worldview_context_reads_story_bible_without_get_config tests.test_context_manager.TestContextManager.test_get_continuity_context_reads_story_bible_without_get_config tests.test_context_manager.TestContextManager.test_get_state_context_reads_state_snapshot_without_get_config tests.test_context_manager.TestContextManager.test_build_updated_summary_text_reads_existing_summary_without_get_config -v`
Expected: FAIL because the current reader methods still call `get_config()`.

- [ ] **Step 3: Write the minimal implementation**

In `core/context.py`:

- add a helper for Story Bible prompt fields, sourced from `StoryBibleStore`
- add a helper for the state/summary snapshot, sourced from the minimal normalized config fields
- make `get_worldview_context()`, `get_continuity_context()`, `get_state_context()`, and `build_updated_summary_text()` use those helpers
- keep `get_config()` unchanged as a compatibility API

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_get_worldview_context_reads_story_bible_without_get_config tests.test_context_manager.TestContextManager.test_get_continuity_context_reads_story_bible_without_get_config tests.test_context_manager.TestContextManager.test_get_state_context_reads_state_snapshot_without_get_config tests.test_context_manager.TestContextManager.test_build_updated_summary_text_reads_existing_summary_without_get_config -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/context.py tests/test_context_manager.py
git commit -m "feat: detach context readers from legacy config snapshot"
```

## Chunk 2: Regression verification

### Task 2: Run focused and broader regressions

**Files:**
- Test: `tests/test_context_manager.py`
- Test: `tests/test_plot_store.py`
- Test: `tests/test_reviewer.py`

- [ ] **Step 1: Run focused context-reader tests**

Run: `python3 -m unittest tests.test_context_manager tests.test_reviewer -v`
Expected: PASS

- [ ] **Step 2: Run broader origin-pipeline regressions**

Run: `python3 -m unittest tests.test_story_bible_store tests.test_plot_store tests.test_canon_store tests.test_release_policy_store tests.test_episode_artifact_store tests.test_run_snapshot_store tests.test_origin_quality tests.test_context_manager tests.test_generator_storage tests.test_chapter_source tests.test_automation_store tests.test_automation_runtime tests.test_automation_ui tests.test_diagnostics_ui tests.test_automator tests.test_canon_extractor tests.test_publishing_executor tests.test_publishing_runtime tests.test_token_budget tests.test_ui_helpers tests.test_reviewer -v`
Expected: PASS

- [ ] **Step 3: Run syntax verification**

Run: `python3 -m py_compile core/context.py tests/test_context_manager.py tests/test_reviewer.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-03-14-context-reader-detachment.md
git commit -m "docs: add context reader detachment plan"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-14-context-reader-detachment.md`. Ready to execute?
