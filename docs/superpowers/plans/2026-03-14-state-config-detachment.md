# State Config Detachment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detach `state` and `summary_of_previous` from the general `save_config(...)` write contract while keeping `get_config()` as a merged compatibility view.

**Architecture:** Keep `ContextStateStore` as the source of truth for state fields and make `ContextManager.save_config(...)` update only the Story Bible compatibility fields. Adjust tests so state/summary seeding uses dedicated APIs, and add a focused regression proving `save_config(...)` no longer overwrites state-store-backed values.

**Tech Stack:** Python, unittest, existing `ContextManager`, `ContextStateStore`, legacy `config.json` compatibility shadow

---

## Chunk 1: Save-config detachment tests

### Task 1: Add failing tests for the new write contract

**Files:**
- Modify: `tests/test_context_manager.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_save_config_ignores_state_fields_and_preserves_existing_context_state_store_value():
    ...

def test_save_config_does_not_create_context_state_store_from_state_fields():
    ...
```

The first test should seed `ContextStateStore` with existing values, call `save_config(...)` with conflicting `state` / `summary_of_previous`, and assert the stored values stay unchanged.

The second test should call `save_config(...)` with `state` / `summary_of_previous` when no state store exists and assert no state store is created and no legacy state shadow is changed from the default snapshot.

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_save_config_ignores_state_fields_and_preserves_existing_context_state_store_value tests.test_context_manager.TestContextManager.test_save_config_does_not_create_context_state_store_from_state_fields -v`
Expected: FAIL because `save_config(...)` still writes `state` and `summary_of_previous` into legacy config.

- [ ] **Step 3: Write the minimal implementation**

In `core/context.py`:

- change `save_config(...)` so it only updates:
  - `worldview`
  - `tone_and_manner`
  - `continuity`
- preserve existing legacy state shadow values instead of replacing them from `config_data`
- keep `get_config()` unchanged as a merged read compatibility view

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_save_config_ignores_state_fields_and_preserves_existing_context_state_store_value tests.test_context_manager.TestContextManager.test_save_config_does_not_create_context_state_store_from_state_fields -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/context.py tests/test_context_manager.py
git commit -m "feat: detach state fields from config write contract"
```

## Chunk 2: Test alignment and regression verification

### Task 2: Align existing tests with the dedicated state APIs

**Files:**
- Modify: `tests/test_context_manager.py`
- Test: `tests/test_reviewer.py`

- [ ] **Step 1: Update state/summary seeding in context-manager tests**

Where tests currently use:

```python
manager.save_config({
    ...
    "state": "...",
    "summary_of_previous": "...",
})
```

replace that setup with the dedicated APIs:

```python
manager.save_story_bible_sections(...)
manager.save_state("...")
manager.save_previous_summary("...")
```

Only update tests whose intent is state/summary setup, not Story Bible compatibility tests.

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
git add docs/superpowers/plans/2026-03-14-state-config-detachment.md
git commit -m "docs: add state config detachment plan"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-14-state-config-detachment.md`. Ready to execute?
