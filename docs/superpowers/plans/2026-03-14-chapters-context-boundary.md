# Chapters Context Boundary Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route generation, review, and semi-automatic chapter context updates through dedicated state/summary save boundaries instead of bulk `config.json` rewrites.

**Architecture:** Add small pure helpers in `ui/chapters.py` that compute context defaults and persist `state`/`summary_of_previous` through `ContextManager`’s dedicated methods. Keep the existing Streamlit UX and plot-related reads intact, while removing the semi-auto tab’s need to rewrite the full config object.

**Tech Stack:** Python, Streamlit, unittest, existing `ContextManager`, `ui/chapters.py`, `tests/test_ui_helpers.py`

---

## Chunk 1: Helper coverage for chapter context persistence

### Task 1: Add failing tests for chapter context helpers

**Files:**
- Modify: `tests/test_ui_helpers.py`
- Modify: `ui/chapters.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_build_chapter_context_defaults_prefers_ai_suggestions():
    ...

def test_build_chapter_context_defaults_falls_back_to_current_snapshot():
    ...

def test_persist_chapter_context_update_routes_state_and_summary_separately():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_ui_helpers -v`
Expected: FAIL because the new helper functions do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

In `ui/chapters.py`:

- add `build_chapter_context_defaults(...)`
- add `persist_chapter_context_update(...)`
- keep both helpers pure except for the explicit `ContextManager` save calls

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_ui_helpers -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui_helpers.py ui/chapters.py
git commit -m "feat: add chapter context persistence helpers"
```

## Chunk 2: Chapters tab integration

### Task 2: Route generation/review/auto context updates through the helpers

**Files:**
- Modify: `ui/chapters.py`
- Test: `tests/test_ui_helpers.py`

- [ ] **Step 1: Write the failing test or assertion first**

If a new helper assertion is needed, add it before implementation. Prefer helper-level tests over Streamlit render tests.

- [ ] **Step 2: Run the targeted tests to verify they fail for the right reason**

Run: `python3 -m unittest tests.test_ui_helpers -v`
Expected: FAIL only if a new helper contract was added and not implemented yet.

- [ ] **Step 3: Write the minimal implementation**

In `ui/chapters.py`:

- use `generator.ctx.get_workspace_settings()` for context-update default snapshots
- use `build_chapter_context_defaults(...)` for generation and review suggestion textareas
- use `persist_chapter_context_update(...)` for generation/review “프로젝트 컨텍스트에 반영” actions
- replace the semi-auto tab’s `save_config(current_config)` write with `persist_chapter_context_update(...)`

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_ui_helpers -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/chapters.py tests/test_ui_helpers.py
git commit -m "feat: route chapter context updates through dedicated saves"
```

## Chunk 3: Verification

### Task 3: Run focused and broader regressions

**Files:**
- Test: `tests/test_ui_helpers.py`
- Test: `tests/test_context_manager.py`
- Test: `tests/test_automator.py`
- Test: `tests/test_publishing_runtime.py`

- [ ] **Step 1: Run focused helper tests**

Run: `python3 -m unittest tests.test_ui_helpers -v`
Expected: PASS

- [ ] **Step 2: Run broader origin-pipeline regressions**

Run: `python3 -m unittest tests.test_story_bible_store tests.test_canon_store tests.test_release_policy_store tests.test_episode_artifact_store tests.test_run_snapshot_store tests.test_origin_quality tests.test_context_manager tests.test_generator_storage tests.test_chapter_source tests.test_automation_store tests.test_automation_runtime tests.test_automation_ui tests.test_diagnostics_ui tests.test_automator tests.test_canon_extractor tests.test_publishing_executor tests.test_publishing_runtime tests.test_ui_helpers -v`
Expected: PASS

- [ ] **Step 3: Run syntax verification**

Run: `python3 -m py_compile ui/chapters.py tests/test_ui_helpers.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-03-14-chapters-context-boundary.md
git commit -m "docs: add chapters context boundary plan"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-14-chapters-context-boundary.md`. Ready to execute?
