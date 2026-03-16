# Story Bible Compatibility Quarantine Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Story Bible compatibility aliases read as legacy compatibility-only API surface without changing runtime behavior.

**Architecture:** Keep `get_story_bible_settings()`, `save_story_bible_sections(...)`, and `DEFAULT_STORY_BIBLE_SETTINGS` as the primary Story Bible path. Add explicit compatibility markers to `DEFAULT_CONFIG`, `get_config()`, and `save_config(...)`, then reorganize tests so primary-path checks and compatibility-path checks are clearly separated.

**Tech Stack:** Python, unittest, existing `ContextManager`, `StoryBibleStore`, legacy `config.json` shadow compatibility layer

---

## Chunk 1: Mark the compatibility alias surface explicitly

### Task 1: Add explicit compatibility markers to the public alias API

**Files:**
- Modify: `core/context.py`
- Modify: `tests/test_context_manager.py`

- [ ] **Step 1: Write the failing tests**

Add targeted tests that make the compatibility contract explicit:

```python
def test_default_config_alias_points_to_story_bible_defaults():
    self.assertIs(context_module.DEFAULT_CONFIG, context_module.DEFAULT_STORY_BIBLE_SETTINGS)

def test_get_story_bible_settings_docstring_marks_primary_api():
    self.assertIn("primary", ContextManager.get_story_bible_settings.__doc__)

def test_get_config_docstring_marks_compatibility_alias():
    self.assertIn("compatibility", ContextManager.get_config.__doc__)

def test_save_config_docstring_marks_compatibility_alias():
    self.assertIn("compatibility", ContextManager.save_config.__doc__)
```

The alias-identity test should prove `DEFAULT_CONFIG` is not an independent default contract. The docstring tests should prove the code surface itself communicates which APIs are primary and which are legacy compatibility aliases.

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_default_config_alias_points_to_story_bible_defaults tests.test_context_manager.TestContextManager.test_get_story_bible_settings_docstring_marks_primary_api tests.test_context_manager.TestContextManager.test_get_config_docstring_marks_compatibility_alias tests.test_context_manager.TestContextManager.test_save_config_docstring_marks_compatibility_alias -v`

Expected:
- `test_default_config_alias_points_to_story_bible_defaults` may already pass
- the docstring tests should FAIL because the public methods do not yet advertise primary vs compatibility status

If the alias-identity test passes immediately, keep it as a guard and continue the red-green loop with the docstring failures.

- [ ] **Step 3: Write the minimal implementation**

In `core/context.py`:

- add a short primary-path docstring to `get_story_bible_settings()`
- add short compatibility docstrings to `get_config()` and `save_config(...)`
- keep `DEFAULT_CONFIG = DEFAULT_STORY_BIBLE_SETTINGS`
- add a short compatibility comment next to `DEFAULT_CONFIG`
- do not change runtime behavior or return values

Keep the edits local. Do not introduce new helper layers or new APIs.

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_default_config_alias_points_to_story_bible_defaults tests.test_context_manager.TestContextManager.test_get_story_bible_settings_docstring_marks_primary_api tests.test_context_manager.TestContextManager.test_get_config_docstring_marks_compatibility_alias tests.test_context_manager.TestContextManager.test_save_config_docstring_marks_compatibility_alias -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/context.py tests/test_context_manager.py
git commit -m "refactor: mark story bible compatibility aliases"
```

## Chunk 2: Separate primary-path and compatibility-path tests

### Task 2: Reorganize context tests around the primary Story Bible path

**Files:**
- Modify: `tests/test_context_manager.py`
- Test: `tests/test_ui_helpers.py`
- Test: `tests/test_reviewer.py`

- [ ] **Step 1: Write the failing tests or rename guards**

Add or rename tests so the file clearly exposes two groups:

- primary-path tests:
  - `get_story_bible_settings()`
  - `save_story_bible_sections(...)`
  - `DEFAULT_STORY_BIBLE_SETTINGS`
- compatibility-path tests:
  - `get_config()`
  - `save_config(...)`
  - `DEFAULT_CONFIG`

At minimum, add one explicit compatibility-only test:

```python
def test_default_config_alias_points_to_story_bible_defaults():
    ...
```

and keep the existing alias delegation tests:

```python
def test_get_config_alias_matches_story_bible_settings():
    ...

def test_save_config_delegates_to_save_story_bible_sections():
    ...
```

If any test still uses `DEFAULT_CONFIG` or `get_config()` for non-compatibility assertions, rename or rewrite it to use `DEFAULT_STORY_BIBLE_SETTINGS` and `get_story_bible_settings()`.

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
git commit -m "test: separate story bible primary and compatibility paths"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-16-story-bible-compatibility-quarantine.md`. Ready to execute?
