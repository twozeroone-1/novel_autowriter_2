# Plot Config Detachment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove plot fields from the general config contract while keeping plot behavior working through the dedicated plot API and legacy fallback path.

**Architecture:** Keep `plot.json` as the source of truth and make `ContextManager` treat plot as a separate compatibility concern instead of a normal config field. General config methods will normalize and persist only workspace/story fields, while plot reads and writes stay behind `get_plot_outline()` and `save_plot_outline()` with legacy `config.json` fallback/shadow behavior isolated to plot-specific helpers.

**Tech Stack:** Python, unittest, existing `ContextManager`, `PlotStore`, legacy `config.json` compatibility helpers

---

## Chunk 1: General config contract tests

### Task 1: Add failing tests that define the detached plot contract

**Files:**
- Modify: `tests/test_context_manager.py`
- Modify: `core/context.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_get_config_does_not_expose_plot_fields():
    ...

def test_save_config_ignores_plot_fields_and_keeps_existing_plot_store_value():
    ...

def test_get_plot_outline_falls_back_to_raw_legacy_plot_fields_when_plot_store_missing():
    ...
```

The fallback test should simulate a legacy project by writing raw `config.json` plot fields directly, not by using `save_config(...)`.

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_get_config_does_not_expose_plot_fields tests.test_context_manager.TestContextManager.test_save_config_ignores_plot_fields_and_keeps_existing_plot_store_value tests.test_context_manager.TestContextManager.test_get_plot_outline_falls_back_to_raw_legacy_plot_fields_when_plot_store_missing -v`
Expected: FAIL because the current config contract still includes plot fields and tests still rely on `save_config(...)` for plot setup.

- [ ] **Step 3: Write the minimal implementation**

In `core/context.py`:

- remove `plot_outline` and `plot_version` from `DEFAULT_CONFIG`
- keep `_normalize_config(...)` limited to general config fields only
- make `_write_legacy_config(...)` preserve existing extra keys from the raw config payload while normalizing the official config fields
- make `_load_plot_payload(...)` read raw legacy plot fields from `config.json` only inside the plot-specific compatibility path

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_get_config_does_not_expose_plot_fields tests.test_context_manager.TestContextManager.test_save_config_ignores_plot_fields_and_keeps_existing_plot_store_value tests.test_context_manager.TestContextManager.test_get_plot_outline_falls_back_to_raw_legacy_plot_fields_when_plot_store_missing -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/context.py tests/test_context_manager.py
git commit -m "feat: detach plot from general config contract"
```

## Chunk 2: Plot prompt regression updates

### Task 2: Move plot prompt tests onto the dedicated plot API

**Files:**
- Modify: `tests/test_context_manager.py`

- [ ] **Step 1: Write the failing test updates**

Update the existing generation-prompt plot assertions so setup uses:

```python
manager.save_plot_outline("plot outline text")
```

instead of passing `plot_outline` through `save_config(...)`.

- [ ] **Step 2: Run the targeted tests to verify they fail for the right reason**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_build_generation_prompt_includes_all_context_and_plot_when_enabled tests.test_context_manager.TestContextManager.test_build_generation_prompt_omits_plot_block_when_disabled -v`
Expected: FAIL if the tests still assume plot is part of the general config contract.

- [ ] **Step 3: Write the minimal implementation**

Only if needed by the failing tests:

- adjust any remaining helper logic so prompt building still reads plot solely through `get_plot_outline()`
- do not change UI or reviewer call signatures

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_build_generation_prompt_includes_all_context_and_plot_when_enabled tests.test_context_manager.TestContextManager.test_build_generation_prompt_omits_plot_block_when_disabled -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_context_manager.py core/context.py
git commit -m "test: update plot prompt coverage for detached config contract"
```

## Chunk 3: Verification

### Task 3: Run focused and broader regressions

**Files:**
- Test: `tests/test_context_manager.py`
- Test: `tests/test_plot_store.py`
- Test: `tests/test_reviewer.py`

- [ ] **Step 1: Run focused detachment tests**

Run: `python3 -m unittest tests.test_plot_store tests.test_context_manager tests.test_reviewer -v`
Expected: PASS

- [ ] **Step 2: Run broader origin-pipeline regressions**

Run: `python3 -m unittest tests.test_story_bible_store tests.test_plot_store tests.test_canon_store tests.test_release_policy_store tests.test_episode_artifact_store tests.test_run_snapshot_store tests.test_origin_quality tests.test_context_manager tests.test_generator_storage tests.test_chapter_source tests.test_automation_store tests.test_automation_runtime tests.test_automation_ui tests.test_diagnostics_ui tests.test_automator tests.test_canon_extractor tests.test_publishing_executor tests.test_publishing_runtime tests.test_token_budget tests.test_ui_helpers tests.test_reviewer -v`
Expected: PASS

- [ ] **Step 3: Run syntax verification**

Run: `python3 -m py_compile core/context.py tests/test_context_manager.py tests/test_plot_store.py tests/test_reviewer.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-03-14-plot-config-detachment.md
git commit -m "docs: add plot config detachment plan"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-14-plot-config-detachment.md`. Ready to execute?
