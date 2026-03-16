# Story Bible API Detachment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce Story Bible-specific public API names in `ContextManager` and demote `get_config()` / `save_config(...)` / `DEFAULT_CONFIG` to compatibility aliases.

**Architecture:** Add a primary Story Bible read API, route the legacy generic read/write names through it or through `save_story_bible_sections(...)`, and switch tests to prefer the Story Bible-specific API and constants. Keep behavior unchanged while making compatibility status explicit in code.

**Tech Stack:** Python, unittest, existing `ContextManager`, `StoryBibleStore`, legacy `config.json` compatibility shadow

---

## Chunk 1: Primary Story Bible API and compatibility aliases

### Task 1: Add failing tests for the new primary API

**Files:**
- Modify: `tests/test_context_manager.py`
- Modify: `core/context.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_get_story_bible_settings_returns_story_bible_compatibility_view():
    ...

def test_get_config_alias_matches_story_bible_settings():
    ...

def test_save_config_delegates_to_save_story_bible_sections():
    ...
```

The first test should seed Story Bible data and assert the new public reader returns the expected three-field view.

The second should assert `get_config()` returns the same payload as `get_story_bible_settings()`.

The third should patch `save_story_bible_sections(...)` and prove `save_config(...)` acts as a compatibility alias rather than as an independent save path.

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_get_story_bible_settings_returns_story_bible_compatibility_view tests.test_context_manager.TestContextManager.test_get_config_alias_matches_story_bible_settings tests.test_context_manager.TestContextManager.test_save_config_delegates_to_save_story_bible_sections -v`
Expected: FAIL because the new public API does not exist yet and `save_config(...)` does not delegate through `save_story_bible_sections(...)`.

- [ ] **Step 3: Write the minimal implementation**

In `core/context.py`:

- add `get_story_bible_settings()` as the primary Story Bible read API
- make `get_config()` a thin compatibility alias to that method
- make `save_config(...)` normalize the payload and delegate to `save_story_bible_sections(...)`
- add a primary Story Bible defaults constant, for example `DEFAULT_STORY_BIBLE_SETTINGS`, and keep `DEFAULT_CONFIG` as a compatibility alias

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_get_story_bible_settings_returns_story_bible_compatibility_view tests.test_context_manager.TestContextManager.test_get_config_alias_matches_story_bible_settings tests.test_context_manager.TestContextManager.test_save_config_delegates_to_save_story_bible_sections -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/context.py tests/test_context_manager.py
git commit -m "refactor: add story bible compatibility aliases"
```

## Chunk 2: Test migration and regression verification

### Task 2: Prefer the Story Bible-specific API in tests and verify regressions

**Files:**
- Modify: `tests/test_context_manager.py`
- Modify: `tests/test_ui_helpers.py`
- Test: `tests/test_reviewer.py`

- [ ] **Step 1: Migrate non-alias tests to the new API**

Where tests are validating the Story Bible compatibility view rather than the alias itself, switch them to:

```python
manager.get_story_bible_settings()
context_module.DEFAULT_STORY_BIBLE_SETTINGS
```

Keep a small number of explicit alias tests for `get_config()` / `DEFAULT_CONFIG`.

If `tests/test_ui_helpers.py` has fake contexts with unused `get_config()` methods, remove them only if the test no longer needs the alias assertion.

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
git add docs/superpowers/plans/2026-03-16-story-bible-api-detachment.md
git commit -m "docs: add story bible api detachment plan"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-16-story-bible-api-detachment.md`. Ready to execute?
