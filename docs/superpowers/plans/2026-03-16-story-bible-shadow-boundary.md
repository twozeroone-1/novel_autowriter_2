# Story Bible Shadow Boundary Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reframe `ContextManager`'s remaining `config.json` compatibility logic as a Story Bible shadow boundary and route Story Bible writes through one shared helper.

**Architecture:** Keep public behavior unchanged while tightening internal boundaries inside `core/context.py`. Introduce explicit Story Bible shadow helpers and a shared write path used by both `save_config(...)` and `save_story_bible_sections(...)`. Verify the boundary through focused `ContextManager` tests, then run the origin regression suite.

**Tech Stack:** Python, unittest, existing `ContextManager`, `StoryBibleStore`, legacy `config.json` compatibility shadow

---

## Chunk 1: Shared Story Bible shadow write boundary

### Task 1: Add failing tests for the shared helper boundary

**Files:**
- Modify: `tests/test_context_manager.py`
- Modify: `core/context.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_save_config_routes_story_bible_shadow_write_through_shared_helper():
    ...

def test_save_story_bible_sections_routes_story_bible_shadow_write_through_shared_helper():
    ...
```

Use `patch.object(...)` on the new shared helper and assert:

- `save_config(...)` calls it once with the normalized Story Bible fields
- `save_story_bible_sections(...)` calls it once with the provided Story Bible fields

Keep the assertions on `StoryBibleStore` updates in place so the helper boundary test still reflects real behavior.

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_save_config_routes_story_bible_shadow_write_through_shared_helper tests.test_context_manager.TestContextManager.test_save_story_bible_sections_routes_story_bible_shadow_write_through_shared_helper -v`
Expected: FAIL because the shared Story Bible shadow helper does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

In `core/context.py`:

- introduce an explicit Story Bible shadow helper, for example:
  - `_load_story_bible_shadow_payload(...)`
  - `_normalize_story_bible_shadow_payload(...)`
  - `_write_story_bible_shadow(...)`
- keep `DEFAULT_CONFIG` as a compatibility alias if needed, but make the Story Bible shadow meaning explicit in code
- route both `save_config(...)` and `save_story_bible_sections(...)` through the same Story Bible shadow write helper
- keep `state` and `plot` shadow behavior unchanged

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_save_config_routes_story_bible_shadow_write_through_shared_helper tests.test_context_manager.TestContextManager.test_save_story_bible_sections_routes_story_bible_shadow_write_through_shared_helper -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/context.py tests/test_context_manager.py
git commit -m "refactor: clarify story bible shadow boundary"
```

## Chunk 2: Compatibility meaning and regression coverage

### Task 2: Align names and verify compatibility behavior stays intact

**Files:**
- Modify: `core/context.py`
- Modify: `tests/test_context_manager.py`

- [ ] **Step 1: Add or update compatibility tests as needed**

Ensure the existing test set still covers:

- `get_config()` as Story Bible-only compatibility view
- new project `config.json` initialization with Story Bible-only defaults
- `save_story_bible_sections(...)` preserving existing `state` / `summary_of_previous` / `plot_*` shadow fields

If any of those assertions are missing, add the smallest targeted test before changing code further.

- [ ] **Step 2: Run focused regressions**

Run: `python3 -m unittest tests.test_context_manager tests.test_reviewer -v`
Expected: PASS

- [ ] **Step 3: Run broader origin regressions**

Run: `python3 -m unittest tests.test_story_bible_store tests.test_context_state_store tests.test_plot_store tests.test_canon_store tests.test_release_policy_store tests.test_episode_artifact_store tests.test_run_snapshot_store tests.test_origin_quality tests.test_context_manager tests.test_generator_storage tests.test_chapter_source tests.test_automation_store tests.test_automation_runtime tests.test_automation_ui tests.test_diagnostics_ui tests.test_automator tests.test_canon_extractor tests.test_publishing_executor tests.test_publishing_runtime tests.test_token_budget tests.test_ui_helpers tests.test_reviewer -v`
Expected: PASS

- [ ] **Step 4: Run syntax verification**

Run: `python3 -m py_compile core/context.py tests/test_context_manager.py tests/test_reviewer.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-03-16-story-bible-shadow-boundary.md
git commit -m "docs: add story bible shadow boundary plan"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-16-story-bible-shadow-boundary.md`. Ready to execute?
