# Quality Gate Orchestrator v1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated quality gate orchestrator that runs cheap rule validation, cheap structure validation, an optional one-shot low-cost repair, and returns a final publish-or-block decision before the publishing runtime calls the executor.

**Architecture:** Introduce `quality_gate_orchestrator.py` as the pre-publish decision boundary, keep `publishing_quality.py` as the cheap rules gate, add `publishing_structure.py` for deterministic publish-shape checks, and optionally isolate repair prompting in `publishing_repair.py`. Rewire `publishing_runtime.py` to call the orchestrator instead of owning direct quality gating, while preserving snapshots, history writes, release policy behavior, executor filtering, and Canon finalize rules.

**Tech Stack:** Python, unittest, existing `PublishingRuntime`, `PublishingStore`, `RunSnapshotStore`, `core.llm.generate_text`, `origin_quality.validate_origin_draft`, JSON snapshot reporting

---

## File Structure

### New files

- `core/publishing_structure.py`
  - deterministic structure-specific checks for headings, episode numbering mismatch, leftover auxiliary markers, and repeated-line spam
- `core/publishing_repair.py`
  - one-shot low-cost repair helper used only for recoverable quality failures
- `core/quality_gate_orchestrator.py`
  - orchestrates rules gate, structure gate, optional repair, re-check, and final normalized decision
- `tests/test_publishing_structure.py`
  - unit tests for structure-only quality checks
- `tests/test_quality_gate_orchestrator.py`
  - unit tests for orchestrator decisions, repair flow, and final result contract

### Modified files

- `core/publishing_runtime.py`
  - replace direct `evaluate_publish_source(...)` usage with orchestrator call and block-on-hard-fail behavior
- `tests/test_publishing_runtime.py`
  - add coordinator tests for orchestrator hard fail, repaired publishable source, and quality report persistence
- `core/publishing_quality.py`
  - keep as cheap rules gate, but ensure the report remains stable enough for orchestration
- `tests/test_publishing_quality.py`
  - extend only if the rules-gate contract needs normalization support for the orchestrator

### Existing files to reference

- `core/origin_quality.py`
- `core/publishing_incidents.py`
- `core/publishing_executor.py`
- `core/chapter_source.py`
- `core/run_snapshot_store.py`
- `tests/test_origin_quality.py`
- `tests/test_publishing_executor.py`
- `tests/test_release_policy_engine.py`

## Chunk 1: Add deterministic structure validation

### Task 1: Create the structure validator and its tests

**Files:**
- Create: `core/publishing_structure.py`
- Create: `tests/test_publishing_structure.py`

- [ ] **Step 1: Write the failing structure-validator tests**

Create `tests/test_publishing_structure.py` with cases like:

```python
import unittest

from core.publishing_structure import evaluate_publish_structure


class TestPublishingStructure(unittest.TestCase):
    def test_evaluate_publish_structure_returns_pass_for_valid_episode(self):
        report = evaluate_publish_structure(
            {
                "title": "12화. 계약의 대가",
                "content": "# 12화. 계약의 대가\n\n유효한 본문 " * 80,
                "path": "episodes/publishable/ep_012.md",
            }
        )
        self.assertEqual(report["status"], "passed")

    def test_evaluate_publish_structure_returns_retry_possible_for_auxiliary_markers(self):
        report = evaluate_publish_structure(
            {
                "title": "12화. 계약의 대가",
                "content": "# 12화. 계약의 대가\n\n수정본 메모\n\n유효한 본문 " * 50,
            }
        )
        self.assertEqual(report["status"], "retry_possible")

    def test_evaluate_publish_structure_returns_hard_fail_for_episode_number_mismatch(self):
        report = evaluate_publish_structure(
            {
                "title": "12화. 계약의 대가",
                "content": "# 13화. 다른 번호\n\n유효한 본문 " * 80,
            }
        )
        self.assertEqual(report["status"], "hard_fail")

    def test_evaluate_publish_structure_returns_retry_possible_for_repeated_line_spam(self):
        repeated = "같은 줄입니다.\n" * 8
        report = evaluate_publish_structure(
            {
                "title": "12화. 계약의 대가",
                "content": "# 12화. 계약의 대가\n\n" + repeated + ("정상 본문\n" * 80),
            }
        )
        self.assertEqual(report["status"], "retry_possible")
```

- [ ] **Step 2: Run the focused structure tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_structure -v`

Expected: FAIL because `core/publishing_structure.py` does not exist yet.

- [ ] **Step 3: Write the minimal structure validator**

Create `core/publishing_structure.py` with:

- `evaluate_publish_structure(source_payload: dict) -> dict`
- helpers:
  - `_extract_heading_title(...)`
  - `_extract_episode_number(...)`
  - `_has_auxiliary_marker(...)`
  - `_detect_repeated_lines(...)`

Return shape:

```python
{
    "status": "passed" | "retry_possible" | "hard_fail",
    "errors": [...],
    "signals": {
        "heading_present": True,
        "title_episode_number": 12,
        "heading_episode_number": 12,
        "repeated_line_count": 0,
    },
}
```

Minimal rules:

- missing usable heading -> `retry_possible`
- leftover markers such as `초안`, `수정본`, `검수리포트` -> `retry_possible`
- repeated line spam over threshold -> `retry_possible`
- explicit episode-number mismatch between title and heading -> `hard_fail`
- completely non-chapter shaped content -> `hard_fail`

- [ ] **Step 4: Re-run the focused structure tests**

Run: `python3 -m unittest tests.test_publishing_structure -v`

Expected: PASS

- [ ] **Step 5: Commit chunk 1**

```bash
git add core/publishing_structure.py tests/test_publishing_structure.py
git commit -m "feat: add publishing structure validator"
```

## Chunk 2: Add repair helper and orchestrator

### Task 2: Add failing tests for one-shot repair behavior

**Files:**
- Create: `core/publishing_repair.py`
- Create: `core/quality_gate_orchestrator.py`
- Create: `tests/test_quality_gate_orchestrator.py`

- [ ] **Step 1: Write the failing orchestrator tests**

Create `tests/test_quality_gate_orchestrator.py` with cases like:

```python
import unittest
from unittest.mock import patch

from core.quality_gate_orchestrator import evaluate_quality_gate


class TestQualityGateOrchestrator(unittest.TestCase):
    def test_evaluate_quality_gate_returns_publishable_when_rules_and_structure_pass(self):
        result = evaluate_quality_gate(
            {
                "title": "12화. 계약의 대가",
                "content": "# 12화. 계약의 대가\n\n유효한 본문 " * 80,
                "path": "episodes/publishable/ep_012.md",
                "episode_id": "ep_012",
            }
        )
        self.assertEqual(result["status"], "publishable")
        self.assertFalse(result["attempted_repair"])

    @patch("core.quality_gate_orchestrator.repair_publish_source")
    def test_evaluate_quality_gate_repairs_retry_possible_source_once(self, repair_publish_source):
        repair_publish_source.return_value = {
            "title": "12화. 계약의 대가",
            "content": "# 12화. 계약의 대가\n\n정리된 본문 " * 80,
        }
        result = evaluate_quality_gate(
            {
                "title": "12화. 계약의 대가",
                "content": "# 12화. 계약의 대가\n\n수정본 메모\n\n정리 전 본문 " * 50,
                "path": "episodes/publishable/ep_012.md",
                "episode_id": "ep_012",
            }
        )
        self.assertEqual(result["status"], "publishable")
        self.assertTrue(result["attempted_repair"])

    @patch("core.quality_gate_orchestrator.repair_publish_source")
    def test_evaluate_quality_gate_hard_fails_when_repair_still_fails(self, repair_publish_source):
        repair_publish_source.return_value = {
            "title": "12화. 계약의 대가",
            "content": "# 13화. 번호 불일치\n\n여전히 문제 있음",
        }
        result = evaluate_quality_gate(
            {
                "title": "12화. 계약의 대가",
                "content": "# 12화. 계약의 대가\n\n수정본 메모\n\n정리 전 본문 " * 50,
                "path": "episodes/publishable/ep_012.md",
                "episode_id": "ep_012",
            }
        )
        self.assertEqual(result["status"], "hard_fail")
        self.assertTrue(result["attempted_repair"])

    @patch("core.quality_gate_orchestrator.repair_publish_source")
    def test_evaluate_quality_gate_skips_repair_for_immediate_hard_fail(self, repair_publish_source):
        result = evaluate_quality_gate(
            {
                "title": "12화. 계약의 대가",
                "content": "# 99화. 완전히 다른 번호\n\n짧음",
                "path": "episodes/publishable/ep_012.md",
                "episode_id": "ep_012",
            }
        )
        self.assertEqual(result["status"], "hard_fail")
        repair_publish_source.assert_not_called()
```

- [ ] **Step 2: Run the focused orchestrator tests to verify they fail**

Run: `python3 -m unittest tests.test_quality_gate_orchestrator -v`

Expected: FAIL because the orchestrator and repair helper do not exist yet.

- [ ] **Step 3: Write the minimal repair helper**

Create `core/publishing_repair.py` with:

- `repair_publish_source(source_payload: dict, gate_reports: dict) -> dict`
- use `core.llm.generate_text(...)`
- keep the prompt narrow:
  - preserve story meaning
  - remove auxiliary markers
  - normalize heading/title
  - do not invent new scenes

Minimal return:

```python
{
    "title": "...",
    "content": "...",
}
```

The helper should be easy to patch in tests and should not own retry loops.

- [ ] **Step 4: Write the minimal orchestrator**

Create `core/quality_gate_orchestrator.py` with:

- `evaluate_quality_gate(source_payload: dict, *, repair_enabled: bool = True) -> dict`
- helpers:
  - `_merge_repaired_source(...)`
  - `_build_hard_fail_result(...)`
  - `_build_publishable_result(...)`

Required flow:

1. run `evaluate_publish_source(source_payload)`
2. run `evaluate_publish_structure(source_payload)`
3. if either returns immediate unrecoverable failure -> final `hard_fail`
4. if any gate returns `retry_possible` and `repair_enabled`:
   - call `repair_publish_source(...)` once
   - merge repaired title/content into source
   - rerun both gates
5. if repaired source passes both gates -> `publishable`
6. otherwise -> `hard_fail`

Final result contract:

```python
{
    "status": "publishable" | "hard_fail",
    "attempted_repair": False,
    "final_source": {...},
    "gate_reports": {...},
    "errors": [...],
    "repair_summary": {"status": "...", "reason": "..."},
}
```

- [ ] **Step 5: Re-run the focused orchestrator tests**

Run: `python3 -m unittest tests.test_quality_gate_orchestrator tests.test_publishing_structure -v`

Expected: PASS

- [ ] **Step 6: Commit chunk 2**

```bash
git add core/publishing_repair.py core/quality_gate_orchestrator.py tests/test_quality_gate_orchestrator.py
git add core/publishing_structure.py tests/test_publishing_structure.py
git commit -m "feat: add quality gate orchestrator core"
```

## Chunk 3: Rewire publishing runtime to use the orchestrator

### Task 3: Add failing runtime coordinator tests

**Files:**
- Modify: `core/publishing_runtime.py`
- Modify: `tests/test_publishing_runtime.py`

- [ ] **Step 1: Add failing runtime tests around orchestrator integration**

Add tests such as:

```python
def test_tick_blocks_executor_when_orchestrator_returns_hard_fail(self):
    ...

def test_tick_sets_runtime_blocked_for_orchestrator_hard_fail(self):
    ...

def test_tick_uses_orchestrator_final_source_for_executor_payload(self):
    ...

def test_tick_writes_orchestrator_report_to_quality_snapshot(self):
    ...
```

Patch boundaries:

- `evaluate_release_policy`
- `select_runnable_job`
- `evaluate_quality_gate`

Assert:

- executor is not called on orchestrator `hard_fail`
- runtime becomes `blocked`
- history contains orchestrator result
- executor receives repaired `final_source`

- [ ] **Step 2: Run the focused runtime tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_runtime -v`

Expected: FAIL because runtime still calls `evaluate_publish_source(...)` directly.

- [ ] **Step 3: Rewire `PublishingRuntime`**

Modify `core/publishing_runtime.py` to:

- import `evaluate_quality_gate` from `core.quality_gate_orchestrator`
- replace direct `evaluate_publish_source(...)` usage with orchestrator call
- write the full orchestrator report to `quality_report.json`
- on orchestrator `hard_fail`:
  - mark job `failed`
  - set runtime `blocked`
  - persist `last_error`
  - append history with `quality_report` and `publish_quality`
  - skip executor
- on orchestrator `publishable`:
  - continue with executor
  - use `final_source` for downstream payload preparation and report summaries

If needed, add a small helper such as:

```python
def _apply_quality_source_override(source_payload: dict, final_source: dict) -> dict:
    ...
```

- [ ] **Step 4: Re-run the focused runtime tests**

Run: `python3 -m unittest tests.test_publishing_runtime tests.test_quality_gate_orchestrator -v`

Expected: PASS

### Task 4: Run quality and publishing regressions

**Files:**
- No new files; verification only

- [ ] **Step 1: Run the focused quality/publishing suite**

Run:

```bash
python3 -m unittest \
  tests.test_publishing_structure \
  tests.test_quality_gate_orchestrator \
  tests.test_publishing_quality \
  tests.test_publishing_runtime \
  tests.test_publishing_executor \
  tests.test_publishing_incidents \
  tests.test_publishing_canon -v
```

Expected: PASS

- [ ] **Step 2: Run syntax verification for touched modules**

Run:

```bash
python3 -m py_compile \
  core/publishing_structure.py \
  core/publishing_repair.py \
  core/quality_gate_orchestrator.py \
  core/publishing_runtime.py \
  tests/test_publishing_structure.py \
  tests/test_quality_gate_orchestrator.py \
  tests/test_publishing_runtime.py
```

Expected: PASS

- [ ] **Step 3: Commit chunk 3**

```bash
git add core/publishing_runtime.py tests/test_publishing_runtime.py
git commit -m "feat: route publishing runtime through quality gates"
```

## Chunk 4: Full regression and boundary inspection

### Task 5: Run broader regression and inspect residual risks

**Files:**
- No new files; verification only

- [ ] **Step 1: Run the origin/publishing regression suite**

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
  tests.test_token_budget \
  tests.test_ui_helpers \
  tests.test_reviewer -v
```

Expected: PASS

- [ ] **Step 2: Inspect diff scope for quality-gate files only**

Run:

```bash
git diff --stat -- \
  core/publishing_structure.py \
  core/publishing_repair.py \
  core/quality_gate_orchestrator.py \
  core/publishing_runtime.py \
  tests/test_publishing_structure.py \
  tests/test_quality_gate_orchestrator.py \
  tests/test_publishing_runtime.py

git diff --check -- \
  core/publishing_structure.py \
  core/publishing_repair.py \
  core/quality_gate_orchestrator.py \
  core/publishing_runtime.py \
  tests/test_publishing_structure.py \
  tests/test_quality_gate_orchestrator.py \
  tests/test_publishing_runtime.py
```

Expected:

- diff stays within the intended quality slice
- no whitespace errors

- [ ] **Step 3: Summarize residual non-goals**

Record explicitly in the execution summary if these remain intentionally unimplemented:

- critic LLM gate
- episode re-generation
- multi-pass repair loops
- planner-aware narrative checks
- marketing packager
- locale pipeline

- [ ] **Step 4: No extra commit unless verification forces a fix**

If no post-regression fixes are needed, stop here and hand off to execution.

Plan complete and saved to `docs/superpowers/plans/2026-03-16-quality-gate-orchestrator-v1.md`. Ready to execute?
