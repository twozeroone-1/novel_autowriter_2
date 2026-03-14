# Context Store Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewire `ContextManager` and generation prompt assembly so the origin pipeline reads `Story Bible`, `Canon`, and `Release Policy` from the new structured stores while keeping legacy `config.json` compatible for existing UI flows.

**Architecture:** Keep `config.json` as a compatibility layer for mutable short-horizon fields such as `state`, `summary_of_previous`, and `plot_outline`, but move worldview/style/fixed-rules sourcing to `StoryBibleStore`, factual continuity sourcing to `CanonStore`, and policy text sourcing to `ReleasePolicyStore`. The prompt builder should compose these stores into explicit blocks without breaking the current generator API or Streamlit forms.

**Tech Stack:** Python 3, unittest, existing JSON stores

---

### Task 1: Sync `ContextManager` with `StoryBibleStore`

**Files:**
- Modify: `core/context.py`
- Modify: `tests/test_context_manager.py`

- [ ] **Step 1: Write failing tests proving `get_config()` reflects `StoryBibleStore`**
- [ ] **Step 2: Run `python3 -m unittest tests.test_context_manager -v` and verify failure**
- [ ] **Step 3: Implement minimal sync so `worldview`, `tone_and_manner`, and `continuity` read/write through `StoryBibleStore` while preserving legacy config keys**
- [ ] **Step 4: Re-run `python3 -m unittest tests.test_context_manager -v` and verify pass**
- [ ] **Step 5: Commit**

### Task 2: Add Canon and Release Policy prompt blocks

**Files:**
- Modify: `core/context.py`
- Modify: `tests/test_context_manager.py`

- [ ] **Step 1: Write failing tests proving `build_generation_prompt()` includes Canon facts and Release Policy text from the new stores**
- [ ] **Step 2: Run `python3 -m unittest tests.test_context_manager -v` and verify failure**
- [ ] **Step 3: Implement minimal prompt composition helpers for Canon and Release Policy**
- [ ] **Step 4: Re-run `python3 -m unittest tests.test_context_manager -v` and verify pass**
- [ ] **Step 5: Commit**

### Task 3: Verify adjacent generator behavior

**Files:**
- Verify only

- [ ] **Step 1: Run `python3 -m unittest tests.test_context_manager tests.test_generator_storage -v`**
- [ ] **Step 2: Run `python3 -m py_compile core/context.py core/generator.py`**
- [ ] **Step 3: Commit any final integration fix if needed**
