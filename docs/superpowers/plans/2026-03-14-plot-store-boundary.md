# Plot Store Boundary Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `plot_outline` and `plot_version` to a dedicated plot store while preserving the existing `ContextManager` plot API and current UI behavior.

**Architecture:** Add a small `PlotStore` with its own `plot.json` payload and keep all existing callers going through `ContextManager.get_plot_outline()` and `save_plot_outline()`. `ContextManager` becomes the compatibility layer: it reads from the new store first, falls back to legacy `config.json` only when needed, and shadow-writes legacy plot fields so older paths stay intact during the transition.

**Tech Stack:** Python, unittest, existing `ContextManager`, new `PlotStore`, Streamlit callers that already use the plot API

---

## Chunk 1: PlotStore foundation

### Task 1: Add the plot store and its tests

**Files:**
- Create: `core/plot_store.py`
- Create: `tests/test_plot_store.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_load_returns_default_plot_payload_when_missing():
    ...

def test_save_normalizes_payload_and_round_trips():
    ...

def test_bump_version_increments_from_current_value():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_plot_store -v`
Expected: FAIL because `core.plot_store` does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

In `core/plot_store.py`:

- add `DEFAULT_PLOT`
- add `PlotStore.plot_path`
- add `PlotStore.load()`
- add `PlotStore.save(payload)`
- add `PlotStore.bump_version(plot_outline)` that loads the current payload, increments the version safely, and saves the new outline/version

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_plot_store -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/plot_store.py tests/test_plot_store.py
git commit -m "feat: add dedicated plot store"
```

## Chunk 2: ContextManager compatibility layer

### Task 2: Rewire plot reads/writes through the dedicated store

**Files:**
- Modify: `core/context.py`
- Modify: `tests/test_context_manager.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_get_plot_outline_prefers_plot_store_over_legacy_config():
    ...

def test_get_plot_outline_falls_back_to_legacy_config_when_plot_store_missing():
    ...

def test_save_plot_outline_updates_plot_store_and_legacy_shadow_fields():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_get_plot_outline_prefers_plot_store_over_legacy_config tests.test_context_manager.TestContextManager.test_get_plot_outline_falls_back_to_legacy_config_when_plot_store_missing tests.test_context_manager.TestContextManager.test_save_plot_outline_updates_plot_store_and_legacy_shadow_fields -v`
Expected: FAIL because `ContextManager` still reads and writes plot data only through `config.json`.

- [ ] **Step 3: Write the minimal implementation**

In `core/context.py`:

- instantiate `PlotStore`
- make `get_plot_outline()` read `plot.json` first and legacy config second
- make `save_plot_outline()` bump the version in `PlotStore`
- shadow-write `plot_outline` and `plot_version` to legacy `config.json` without routing through `save_config(...)`

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_get_plot_outline_prefers_plot_store_over_legacy_config tests.test_context_manager.TestContextManager.test_get_plot_outline_falls_back_to_legacy_config_when_plot_store_missing tests.test_context_manager.TestContextManager.test_save_plot_outline_updates_plot_store_and_legacy_shadow_fields -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/context.py tests/test_context_manager.py
git commit -m "feat: route plot outline through dedicated store"
```

## Chunk 3: Plot prompt regressions

### Task 3: Verify prompt and reviewer behavior still work through the unchanged API

**Files:**
- Modify: `tests/test_context_manager.py`
- Modify: `tests/test_reviewer.py`

- [ ] **Step 1: Write the failing test adjustments if needed**

If any prompt/reviewer regression needs a new test, add it before implementation. Prefer proving behavior through `save_plot_outline(...)` rather than direct legacy config mutation where possible.

- [ ] **Step 2: Run the targeted tests to verify they fail for the right reason**

Run: `python3 -m unittest tests.test_context_manager tests.test_reviewer -v`
Expected: FAIL only if a new regression assertion was added and the implementation is not complete yet.

- [ ] **Step 3: Write the minimal implementation**

Only if required by the failing tests:

- adjust prompt-building or compatibility glue so `build_generation_prompt(... include_plot=True ...)` and reviewer plot blocks still include the saved plot text
- avoid changing UI workflows or public call signatures

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_context_manager tests.test_reviewer -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_context_manager.py tests/test_reviewer.py core/context.py
git commit -m "test: cover plot store prompt regressions"
```

## Chunk 4: Verification

### Task 4: Run focused and broader regressions

**Files:**
- Test: `tests/test_plot_store.py`
- Test: `tests/test_context_manager.py`
- Test: `tests/test_reviewer.py`

- [ ] **Step 1: Run focused plot-boundary tests**

Run: `python3 -m unittest tests.test_plot_store tests.test_context_manager tests.test_reviewer -v`
Expected: PASS

- [ ] **Step 2: Run broader origin-pipeline regressions**

Run: `python3 -m unittest tests.test_story_bible_store tests.test_plot_store tests.test_canon_store tests.test_release_policy_store tests.test_episode_artifact_store tests.test_run_snapshot_store tests.test_origin_quality tests.test_context_manager tests.test_generator_storage tests.test_chapter_source tests.test_automation_store tests.test_automation_runtime tests.test_automation_ui tests.test_diagnostics_ui tests.test_automator tests.test_canon_extractor tests.test_publishing_executor tests.test_publishing_runtime tests.test_token_budget tests.test_ui_helpers tests.test_reviewer -v`
Expected: PASS

- [ ] **Step 3: Run syntax verification**

Run: `python3 -m py_compile core/plot_store.py core/context.py tests/test_plot_store.py tests/test_context_manager.py tests/test_reviewer.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-03-14-plot-store-boundary.md
git commit -m "docs: add plot store boundary plan"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-14-plot-store-boundary.md`. Ready to execute?
