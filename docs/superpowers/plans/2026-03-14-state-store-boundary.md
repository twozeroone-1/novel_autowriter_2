# State Store Boundary Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `state` and `summary_of_previous` to a dedicated structured store while keeping legacy `config.json` as a compatibility shadow.

**Architecture:** Add a small `ContextStateStore` with a single responsibility: normalize and persist the current `state` and `summary_of_previous` snapshot. Rewire `ContextManager` so state readers and writers use that store as the primary source of truth, with lazy fallback from legacy `config.json` and shadow writes back to `config.json` for compatibility.

**Tech Stack:** Python, unittest, existing `ContextManager`, structured project data stores, legacy `config.json` compatibility layer

---

## Chunk 1: Dedicated state store foundation

### Task 1: Add the new structured store with TDD

**Files:**
- Create: `core/context_state_store.py`
- Create: `tests/test_context_state_store.py`

- [ ] **Step 1: Write the failing store tests**

Add tests for:

```python
def test_load_returns_default_state_payload_when_missing():
    ...

def test_save_normalizes_payload_and_round_trips():
    ...

def test_save_preserves_defaults_for_missing_fields():
    ...
```

- [ ] **Step 2: Run the targeted store tests to verify they fail**

Run: `python3 -m unittest tests.test_context_state_store -v`
Expected: FAIL because the store file does not exist yet.

- [ ] **Step 3: Write the minimal store implementation**

In `core/context_state_store.py`:

- add `DEFAULT_CONTEXT_STATE`
- add `ContextStateStore` with:
  - `context_state_path`
  - `load()`
  - `save(payload)`
- add `_normalize_context_state(payload)`

The store should:

- read/write `data/projects/<project>/context_state.json`
- normalize only `state` and `summary_of_previous`
- return default values when missing, invalid, or malformed

- [ ] **Step 4: Run the targeted store tests to verify they pass**

Run: `python3 -m unittest tests.test_context_state_store -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/context_state_store.py tests/test_context_state_store.py
git commit -m "feat: add dedicated context state store"
```

## Chunk 2: ContextManager state boundary rewiring

### Task 2: Rewire state readers and writers to use the new store

**Files:**
- Modify: `core/context.py`
- Modify: `tests/test_context_manager.py`
- Create or modify: `tests/test_context_state_store.py`

- [ ] **Step 1: Write the failing context-manager tests**

Add tests for:

```python
def test_save_state_updates_state_store_and_legacy_shadow():
    ...

def test_save_previous_summary_updates_state_store_and_legacy_shadow():
    ...

def test_get_workspace_settings_prefers_context_state_store_over_legacy_config():
    ...

def test_get_workspace_settings_falls_back_to_legacy_state_when_state_store_missing():
    ...
```

Each test should seed the project using dedicated paths, then assert store-first behavior explicitly.

- [ ] **Step 2: Run the targeted context-manager tests to verify they fail**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_save_state_updates_state_store_and_legacy_shadow tests.test_context_manager.TestContextManager.test_save_previous_summary_updates_state_store_and_legacy_shadow tests.test_context_manager.TestContextManager.test_get_workspace_settings_prefers_context_state_store_over_legacy_config tests.test_context_manager.TestContextManager.test_get_workspace_settings_falls_back_to_legacy_state_when_state_store_missing -v`
Expected: FAIL because `ContextManager` still reads/writes state via legacy `config.json`.

- [ ] **Step 3: Write the minimal implementation**

In `core/context.py`:

- import `ContextStateStore` and instantiate it in `ContextManager.__init__`
- add a helper for writing the legacy state shadow only
- make `_get_state_snapshot()`:
  - use `ContextStateStore.load()` when the store exists
  - otherwise read `state` / `summary_of_previous` from legacy normalized config
- make `save_state(...)` and `save_previous_summary(...)`:
  - load the current state-store payload
  - update only the target field
  - save the store payload
  - shadow-write the same field into `config.json`
- make `get_workspace_settings()` compose Story Bible + state store snapshot
- keep `get_config()` as a compatibility view

- [ ] **Step 4: Run the targeted context-manager tests to verify they pass**

Run: `python3 -m unittest tests.test_context_manager.TestContextManager.test_save_state_updates_state_store_and_legacy_shadow tests.test_context_manager.TestContextManager.test_save_previous_summary_updates_state_store_and_legacy_shadow tests.test_context_manager.TestContextManager.test_get_workspace_settings_prefers_context_state_store_over_legacy_config tests.test_context_manager.TestContextManager.test_get_workspace_settings_falls_back_to_legacy_state_when_state_store_missing -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/context.py tests/test_context_manager.py
git commit -m "feat: route context state through dedicated store"
```

## Chunk 3: Regression verification

### Task 3: Prove the new boundary does not break origin flows

**Files:**
- Test: `tests/test_context_state_store.py`
- Test: `tests/test_context_manager.py`
- Test: `tests/test_reviewer.py`

- [ ] **Step 1: Run focused regressions**

Run: `python3 -m unittest tests.test_context_state_store tests.test_context_manager tests.test_reviewer -v`
Expected: PASS

- [ ] **Step 2: Run broader origin regressions**

Run: `python3 -m unittest tests.test_story_bible_store tests.test_context_state_store tests.test_plot_store tests.test_canon_store tests.test_release_policy_store tests.test_episode_artifact_store tests.test_run_snapshot_store tests.test_origin_quality tests.test_context_manager tests.test_generator_storage tests.test_chapter_source tests.test_automation_store tests.test_automation_runtime tests.test_automation_ui tests.test_diagnostics_ui tests.test_automator tests.test_canon_extractor tests.test_publishing_executor tests.test_publishing_runtime tests.test_token_budget tests.test_ui_helpers tests.test_reviewer -v`
Expected: PASS

- [ ] **Step 3: Run syntax verification**

Run: `python3 -m py_compile core/context_state_store.py core/context.py tests/test_context_state_store.py tests/test_context_manager.py tests/test_reviewer.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-03-14-state-store-boundary.md
git commit -m "docs: add state store boundary plan"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-14-state-store-boundary.md`. Ready to execute?
