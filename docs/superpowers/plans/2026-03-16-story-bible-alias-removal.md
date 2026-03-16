# Story Bible Alias Removal Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the generic Story Bible compatibility aliases from `ContextManager` and leave only the primary Story Bible public contract.

**Architecture:** Delete `DEFAULT_CONFIG`, `get_config()`, and `save_config(...)` from `core/context.py` while keeping the `config.json` shadow helpers private. Then rewrite the context manager tests so they validate only the primary Story Bible API and the separated state/plot boundaries.

**Tech Stack:** Python, unittest, existing `ContextManager`, `StoryBibleStore`, `ContextStateStore`, `PlotStore`, legacy `config.json` shadow helpers

---

## Chunk 1: Remove the public alias surface

### Task 1: Delete the generic Story Bible aliases from `ContextManager`

**Files:**
- Modify: `core/context.py`
- Modify: `tests/test_context_manager.py`

- [ ] **Step 1: Write the failing removal tests**

Add targeted tests that lock in the removal:

```python
def test_context_module_no_longer_exports_default_config_alias(self):
    self.assertFalse(hasattr(context_module, "DEFAULT_CONFIG"))

def test_context_manager_no_longer_exposes_get_config_alias(self):
    self.assertFalse(hasattr(ContextManager, "get_config"))

def test_context_manager_no_longer_exposes_save_config_alias(self):
    self.assertFalse(hasattr(ContextManager, "save_config"))
```

Keep the tests minimal. These should assert the public alias surface is gone, not just deprecated.

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_context_module_no_longer_exports_default_config_alias tests.test_context_manager.TestContextManager.test_context_manager_no_longer_exposes_get_config_alias tests.test_context_manager.TestContextManager.test_context_manager_no_longer_exposes_save_config_alias -v`

Expected: FAIL because the alias constant and methods still exist.

- [ ] **Step 3: Write the minimal implementation**

In `core/context.py`:

- remove `DEFAULT_CONFIG`
- remove `get_config()`
- remove `save_config(...)`
- keep `DEFAULT_STORY_BIBLE_SETTINGS`
- keep `get_story_bible_settings()`
- keep `save_story_bible_sections(...)`
- do not change the shadow helper behavior or state/plot helpers

Do not add a shim. The whole point of this step is that the generic alias surface disappears.

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_context_module_no_longer_exports_default_config_alias tests.test_context_manager.TestContextManager.test_context_manager_no_longer_exposes_get_config_alias tests.test_context_manager.TestContextManager.test_context_manager_no_longer_exposes_save_config_alias -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/context.py tests/test_context_manager.py
git commit -m "refactor: remove story bible config aliases"
```

## Chunk 2: Rewrite tests around the primary Story Bible contract

### Task 2: Replace alias-based tests with primary-path boundary tests

**Files:**
- Modify: `tests/test_context_manager.py`
- Test: `tests/test_ui_helpers.py`
- Test: `tests/test_reviewer.py`

- [ ] **Step 1: Write the failing primary-path tests**

Remove or rewrite every test that still depends on:

- `DEFAULT_CONFIG`
- `get_config()`
- `save_config(...)`

Replace alias-centric coverage with primary-path coverage. Add or update tests such as:

```python
def test_save_story_bible_sections_does_not_modify_context_state_store(self):
    ...

def test_save_story_bible_sections_does_not_modify_plot_store(self):
    ...

def test_get_worldview_context_reads_story_bible_prompt_fields_without_public_settings_view(self):
    ...

def test_get_state_context_reads_state_snapshot_without_workspace_settings(self):
    ...
```

Guidelines for the replacements:

- use `DEFAULT_STORY_BIBLE_SETTINGS`
- use `get_story_bible_settings()`
- use `save_story_bible_sections(...)`
- if a current test patches `get_config()` to prove it is not used, rewrite it to patch the more relevant primary helper instead:
  - `get_story_bible_settings()` for Story Bible read paths
  - `get_workspace_settings()` for state/summary read paths

The new tests should prove separated boundaries, not generic-input ignoring.

- [ ] **Step 2: Run focused regressions**

Run: `python3 -m unittest tests.test_context_manager tests.test_ui_helpers tests.test_reviewer -v`

Expected: PASS

- [ ] **Step 3: Run broader origin regressions**

Run: `python3 -m unittest tests.test_story_bible_store tests.test_context_state_store tests.test_plot_store tests.test_canon_store tests.test_release_policy_store tests.test_episode_artifact_store tests.test_run_snapshot_store tests.test_origin_quality tests.test_context_manager tests.test_generator_storage tests.test_chapter_source tests.test_automation_store tests.test_automation_runtime tests.test_automation_ui tests.test_diagnostics_ui tests.test_automator tests.test_canon_extractor tests.test_publishing_executor tests.test_publishing_runtime tests.test_token_budget tests.test_ui_helpers tests.test_reviewer -v`

Expected: PASS

- [ ] **Step 4: Run syntax verification**

Run: `python3 -m py_compile core/context.py tests/test_context_manager.py tests/test_ui_helpers.py tests/test_reviewer.py`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/context.py tests/test_context_manager.py
git commit -m "test: rewrite story bible coverage around primary api"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-16-story-bible-alias-removal.md`. Ready to execute?
