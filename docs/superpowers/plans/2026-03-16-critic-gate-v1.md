# Critic Gate V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a final LLM-based critic gate that runs after cheap publish validation and blocks platform upload when a draft is not narratively publish-ready.

**Architecture:** Keep the critic as a dedicated module so `quality_gate_orchestrator` remains the only quality decision boundary and `publishing_runtime` stays a coordinator. The flow is `rules -> structure -> optional repair -> critic -> publish/block`, with critic failures persisted into the existing quality snapshot.

**Tech Stack:** Python, unittest, `core.llm.generate_text`, existing `quality_gate_orchestrator`, `publishing_runtime`, and run snapshots

---

## File Structure

### New files

- `core/publishing_critic.py`
  - single-pass LLM critic boundary
- `tests/test_publishing_critic.py`
  - focused unit tests for critic normalization and failure handling

### Modified files

- `core/quality_gate_orchestrator.py`
  - add critic evaluation after cheap gates pass
- `core/publishing_runtime.py`
  - consume critic-aware orchestrator report without new runtime logic leakage
- `tests/test_quality_gate_orchestrator.py`
  - assert critic integration behavior
- `tests/test_publishing_runtime.py`
  - assert runtime blocks executor and persists critic report

## Chunk 1: Add the critic module

### Task 1: Create the focused critic tests first

**Files:**
- Create: `core/publishing_critic.py`
- Create: `tests/test_publishing_critic.py`

- [ ] **Step 1: Write the failing critic tests**

Create `tests/test_publishing_critic.py` with cases that lock:

- `evaluate_publish_critic(...)` returns `passed` for valid JSON critic output
- returns `blocked` for explicit blocking output
- returns `critic_unavailable` when `generate_text` raises `LLMError`
- returns `critic_unavailable` when the model output is not valid JSON

- [ ] **Step 2: Run the focused critic tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_critic -v`

Expected: FAIL because `core/publishing_critic.py` does not exist yet.

- [ ] **Step 3: Implement the minimal critic module**

Create `core/publishing_critic.py` with:

- `DEFAULT_CRITIC_REPORT`
- `_build_critic_prompt(final_source: dict, episode_plan: dict | None) -> str`
- `_normalize_critic_payload(payload: dict | None) -> dict`
- `evaluate_publish_critic(final_source: dict, *, episode_plan: dict | None = None) -> dict`

Rules:

- call `generate_text(..., feature="publish_critic", temperature=0.2)`
- parse with `_extract_first_json_value(..., expected_type=dict)`
- return only `passed`, `blocked`, or `critic_unavailable`
- catch `LLMError` and bad JSON as `critic_unavailable`
- keep `raw_excerpt` short and serializable

- [ ] **Step 4: Re-run the focused critic tests**

Run: `python3 -m unittest tests.test_publishing_critic -v`

Expected: PASS

- [ ] **Step 5: Commit chunk 1**

```bash
git add core/publishing_critic.py tests/test_publishing_critic.py
git commit -m "feat: add publish critic gate"
```

## Chunk 2: Integrate critic into the orchestrator

### Task 2: Add orchestrator tests first

**Files:**
- Modify: `core/quality_gate_orchestrator.py`
- Modify: `tests/test_quality_gate_orchestrator.py`

- [ ] **Step 1: Write the failing orchestrator integration tests**

Extend `tests/test_quality_gate_orchestrator.py` with cases that lock:

- critic is called only when cheap gates pass
- critic `blocked` produces final `hard_fail`
- critic `critic_unavailable` produces final `hard_fail`
- final report includes `critic` inside `gate_reports`

- [ ] **Step 2: Run the focused orchestrator tests to verify they fail**

Run: `python3 -m unittest tests.test_quality_gate_orchestrator -v`

Expected: FAIL because critic integration does not exist yet.

- [ ] **Step 3: Implement orchestrator integration**

Update `core/quality_gate_orchestrator.py`:

- import `evaluate_publish_critic`
- accept optional `episode_plan: dict | None = None` on `evaluate_quality_gate(...)`
- after cheap gates pass, call critic once
- if critic passes, return `publishable`
- if critic blocks or is unavailable, return `hard_fail`
- persist critic report inside `gate_reports`
- include critic issues in `errors`

- [ ] **Step 4: Re-run the focused orchestrator tests**

Run: `python3 -m unittest tests.test_quality_gate_orchestrator tests.test_publishing_critic -v`

Expected: PASS

- [ ] **Step 5: Commit chunk 2**

```bash
git add core/quality_gate_orchestrator.py tests/test_quality_gate_orchestrator.py
git commit -m "feat: route publishable drafts through critic gate"
```

## Chunk 3: Wire critic-aware reports into runtime

### Task 3: Update runtime behavior through tests first

**Files:**
- Modify: `core/publishing_runtime.py`
- Modify: `tests/test_publishing_runtime.py`

- [ ] **Step 1: Add failing runtime tests**

Extend `tests/test_publishing_runtime.py` with cases that lock:

- executor is not called when orchestrator returns critic-caused `hard_fail`
- runtime becomes `blocked`
- history persists critic-inclusive `quality_report`
- `quality_report.json` snapshot contains critic report

- [ ] **Step 2: Run the focused runtime tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_runtime -v`

Expected: FAIL because runtime does not yet pass episode plan or preserve critic detail assumptions.

- [ ] **Step 3: Implement the minimal runtime integration**

Update `core/publishing_runtime.py`:

- pass any available `episode_plan` into `evaluate_quality_gate(...)`
- keep runtime failure handling unchanged except that critic-origin hard fails should preserve critic details in `quality_report`

Do not add runtime-side critic prompting or business logic.

- [ ] **Step 4: Re-run the focused runtime tests**

Run: `python3 -m unittest tests.test_publishing_runtime tests.test_quality_gate_orchestrator tests.test_publishing_critic -v`

Expected: PASS

- [ ] **Step 5: Commit chunk 3**

```bash
git add core/publishing_runtime.py tests/test_publishing_runtime.py
git commit -m "feat: persist critic gate outcomes in publishing runtime"
```

## Chunk 4: Regression verification

### Task 4: Run regressions and syntax checks

**Files:**
- No new files; verification only

- [ ] **Step 1: Run focused critic-quality-runtime regressions**

Run:

```bash
python3 -m unittest \
  tests.test_publishing_critic \
  tests.test_quality_gate_orchestrator \
  tests.test_publishing_runtime -v
```

Expected: PASS

- [ ] **Step 2: Run broader origin/publishing regressions**

Run:

```bash
python3 -m unittest \
  tests.test_story_bible_store \
  tests.test_context_state_store \
  tests.test_plot_store \
  tests.test_canon_store \
  tests.test_release_policy_store \
  tests.test_episode_artifact_store \
  tests.test_run_snapshot_store \
  tests.test_origin_quality \
  tests.test_context_manager \
  tests.test_generator_storage \
  tests.test_generator_planning \
  tests.test_chapter_source \
  tests.test_automation_store \
  tests.test_automation_runtime \
  tests.test_automation_ui \
  tests.test_diagnostics_ui \
  tests.test_automator \
  tests.test_canon_extractor \
  tests.test_publishing_executor \
  tests.test_release_policy_engine \
  tests.test_publishing_policy \
  tests.test_publishing_runtime \
  tests.test_publishing_structure \
  tests.test_quality_gate_orchestrator \
  tests.test_publishing_quality \
  tests.test_publishing_incidents \
  tests.test_publishing_canon \
  tests.test_publishing_critic \
  tests.test_token_budget \
  tests.test_ui_helpers \
  tests.test_reviewer \
  tests.test_planner \
  tests.test_episode_planner -v
```

Expected: PASS

- [ ] **Step 3: Run syntax and diff checks**

Run:

```bash
python3 -m py_compile \
  core/publishing_critic.py \
  core/quality_gate_orchestrator.py \
  core/publishing_runtime.py \
  tests/test_publishing_critic.py \
  tests/test_quality_gate_orchestrator.py \
  tests/test_publishing_runtime.py

git diff --check -- \
  core/publishing_critic.py \
  core/quality_gate_orchestrator.py \
  core/publishing_runtime.py \
  tests/test_publishing_critic.py \
  tests/test_quality_gate_orchestrator.py \
  tests/test_publishing_runtime.py
```

Expected: no syntax errors, no whitespace errors
