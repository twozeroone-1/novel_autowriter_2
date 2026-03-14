# State Read Detachment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `get_config()` a Story Bible-only compatibility read API and keep `get_workspace_settings()` as the only public snapshot that includes `state` and `summary_of_previous`.

**Architecture:** Narrow `ContextManager`'s config normalization and defaulting logic so `config.json` read helpers only manage Story Bible fields. Keep legacy state fallback inside `_get_state_snapshot()`, but stop merging that snapshot into `get_config()`. Update tests to assert the new contract directly and keep UI helper fakes aligned with `get_workspace_settings()`.

**Tech Stack:** Python, unittest, existing `ContextManager`, `ContextStateStore`, Streamlit helper tests

---

## Chunk 1: Read-contract regression coverage

### Task 1: Add failing tests for the detached read contract

**Files:**
- Modify: `tests/test_context_manager.py`
- Modify: `tests/test_ui_helpers.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_get_config_does_not_expose_state_fields():
    ...

def test_get_workspace_settings_includes_state_fields_from_context_state_store():
    ...
```

Update existing assertions that currently read `manager.get_config()["state"]` or `manager.get_config()["summary_of_previous"]` so they use `get_workspace_settings()` when the intent is workspace snapshot verification.

If any fake context in `tests/test_ui_helpers.py` still treats `get_config()` as the state source, update that test to consume `get_workspace_settings()` instead.

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_get_config_does_not_expose_state_fields tests.test_context_manager.TestContextManager.test_get_workspace_settings_includes_state_fields_from_context_state_store -v`
Expected: FAIL because `get_config()` still merges the state snapshot into the returned payload.

- [ ] **Step 3: Write the minimal implementation**

In `core/context.py`:

- shrink `DEFAULT_CONFIG` to Story Bible compatibility defaults only
- import and use `DEFAULT_CONTEXT_STATE` from `core.context_state_store`
- keep `_get_state_snapshot()` fallback behavior, but use `DEFAULT_CONTEXT_STATE` for `state` defaults
- remove `_merge_state_snapshot_into_config(...)` from the `get_config()` path
- keep `get_workspace_settings()` as the only public method that merges Story Bible fields with the state snapshot

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_get_config_does_not_expose_state_fields tests.test_context_manager.TestContextManager.test_get_workspace_settings_includes_state_fields_from_context_state_store -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/context.py tests/test_context_manager.py tests/test_ui_helpers.py
git commit -m "feat: detach state fields from config read contract"
```

## Chunk 2: Broader test alignment and verification

### Task 2: Align remaining tests and run regressions

**Files:**
- Modify: `tests/test_context_manager.py`
- Modify: `tests/test_ui_helpers.py`
- Test: `tests/test_reviewer.py`

- [ ] **Step 1: Finish replacing legacy snapshot assertions**

Where existing tests still validate state/summary through `get_config()`, move those assertions to:

```python
workspace_settings = manager.get_workspace_settings()
```

Keep Story Bible assertions on `get_config()` unchanged.

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
git add docs/superpowers/plans/2026-03-14-state-read-detachment.md
git commit -m "docs: add state read detachment plan"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-14-state-read-detachment.md`. Ready to execute?
