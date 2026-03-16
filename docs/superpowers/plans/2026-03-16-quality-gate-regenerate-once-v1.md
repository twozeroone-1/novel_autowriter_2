# Quality Gate Regenerate-Once V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded one-shot full regeneration path to the publish quality gates so the system can retry narrative failures once with the same `episode_plan` before declaring final `hard_fail`.

**Architecture:** Keep `quality_gate_orchestrator.py` as the single quality decision boundary and add a narrow `publishing_regenerate.py` helper for regeneration mechanics. The orchestrator should decide when regeneration is allowed, invoke it at most once, re-run cheap gates plus critic on the regenerated draft, and return the same final runtime-facing statuses as today.

**Tech Stack:** Python, unittest, existing `core.llm.generate_text`, `core.llm._extract_first_json_value`, `Episode Planner v1`, `PublishingRuntime`, JSON quality snapshots

---

## File Structure

### New files

- `core/publishing_regenerate.py`
  - one-shot full-regeneration helper using the existing `episode_plan`
- `tests/test_publishing_regenerate.py`
  - focused unit tests for regeneration prompt/result normalization and failure handling

### Modified files

- `core/quality_gate_orchestrator.py`
  - add regenerateability classification, injected `regenerate_fn`, regenerate-aware report building, and one-shot regeneration flow
- `tests/test_quality_gate_orchestrator.py`
  - add regenerate-once tests and update expectations for richer result payloads
- `tests/test_publishing_runtime.py`
  - add coordinator tests proving runtime consumes regenerate-aware reports without new business logic

### Existing files to reference

- `core/publishing_quality.py`
- `core/publishing_structure.py`
- `core/publishing_repair.py`
- `core/publishing_critic.py`
- `core/generator.py`
- `core/episode_planner.py`
- `core/llm.py`
- `core/publishing_runtime.py`

## Chunk 1: Add the regeneration helper

### Task 1: Create failing regeneration-helper tests

**Files:**
- Create: `tests/test_publishing_regenerate.py`
- Create: `core/publishing_regenerate.py`

- [ ] **Step 1: Write the failing regeneration-helper tests**

Create `tests/test_publishing_regenerate.py` with cases like:

```python
import unittest
from unittest.mock import patch

from core.publishing_regenerate import regenerate_publish_source


class TestPublishingRegenerate(unittest.TestCase):
    @patch("core.publishing_regenerate.generate_text")
    def test_regenerate_publish_source_reuses_same_episode_plan(self, generate_text):
        generate_text.return_value = """
        {
          "title": "12화. 계약의 대가",
          "content": "# 12화. 계약의 대가\\n\\n재생성된 본문",
          "regeneration_summary": "critic blocked draft regenerated once"
        }
        """

        episode_plan = {"episode_objective": "계약 후폭풍을 수습한다", "target_length": 5000}
        result = regenerate_publish_source(
            {"title": "12화. 계약의 대가", "content": "# 12화. 계약의 대가\\n\\n초안"},
            episode_plan=episode_plan,
            project_name="sample",
            length_goal=5000,
        )

        self.assertEqual(result["title"], "12화. 계약의 대가")
        self.assertIn("재생성된 본문", result["content"])
        self.assertIn("계약 후폭풍을 수습한다", generate_text.call_args.args[0])

    @patch("core.publishing_regenerate.generate_text")
    def test_regenerate_publish_source_normalizes_invalid_json_to_failure_payload(self, generate_text):
        generate_text.return_value = "not json"

        result = regenerate_publish_source(
            {"title": "12화. 계약의 대가", "content": "# 12화. 계약의 대가\\n\\n초안"},
            episode_plan={"episode_objective": "계약 후폭풍을 수습한다"},
            project_name="sample",
        )

        self.assertEqual(result["status"], "failed")
        self.assertIn("invalid json", result["reason"])
```

- [ ] **Step 2: Run the focused regeneration tests and confirm failure**

Run: `python3 -m unittest tests.test_publishing_regenerate -v`

Expected: FAIL because `core/publishing_regenerate.py` does not exist yet.

- [ ] **Step 3: Write the minimal regeneration helper**

Create `core/publishing_regenerate.py` with:

- `regenerate_publish_source(source_payload: dict, *, episode_plan: dict | None, project_name: str | None = None, length_goal: int | None = None) -> dict`
- internal helpers:
  - `_build_regeneration_prompt(...)`
  - `_normalize_regeneration_payload(...)`

Implementation rules:

- use `core.llm.generate_text(...)`
- parse the first JSON object with `core.llm._extract_first_json_value(...)`
- ask for JSON keys:
  - `title`
  - `content`
  - `regeneration_summary`
- preserve the same episode identity and same `episode_plan`
- on backend/parse failure, return:

```python
{
    "status": "failed",
    "reason": "regeneration returned invalid json",
    "title": "",
    "content": "",
    "regeneration_summary": "",
}
```

- on success, return:

```python
{
    "status": "applied",
    "reason": "",
    "title": "...",
    "content": "...",
    "regeneration_summary": "...",
}
```

- [ ] **Step 4: Re-run the focused regeneration tests**

Run: `python3 -m unittest tests.test_publishing_regenerate -v`

Expected: PASS

- [ ] **Step 5: Commit chunk 1**

```bash
git add core/publishing_regenerate.py tests/test_publishing_regenerate.py
git commit -m "feat: add publishing regenerate helper"
```

## Chunk 2: Teach the orchestrator to regenerate once

### Task 2: Write failing orchestrator tests for regenerate-once behavior

**Files:**
- Modify: `tests/test_quality_gate_orchestrator.py`
- Modify: `core/quality_gate_orchestrator.py`

- [ ] **Step 1: Add failing regenerate-once tests**

Extend `tests/test_quality_gate_orchestrator.py` with cases like:

```python
    @patch("core.quality_gate_orchestrator.regenerate_publish_source")
    @patch("core.quality_gate_orchestrator.evaluate_publish_critic")
    def test_evaluate_quality_gate_regenerates_once_when_critic_blocks(
        self,
        evaluate_publish_critic,
        regenerate_publish_source,
    ):
        evaluate_publish_critic.side_effect = [
            {
                "status": "blocked",
                "summary": "objective drift",
                "issues": ["episode objective missing"],
                "model": "gemini-2.5-flash",
                "cost": {"mode": "single_pass"},
                "raw_excerpt": "",
            },
            {
                "status": "passed",
                "summary": "ok",
                "issues": [],
                "model": "gemini-2.5-flash",
                "cost": {"mode": "single_pass"},
                "raw_excerpt": "",
            },
        ]
        regenerate_publish_source.return_value = {
            "status": "applied",
            "reason": "",
            "title": "12화. 계약의 대가",
            "content": "# 12화. 계약의 대가\\n\\n재생성된 정상 본문\\n" * 80,
            "regeneration_summary": "critic-blocked draft regenerated",
        }

        result = evaluate_quality_gate(_valid_source(), episode_plan={"episode_objective": "계약 후폭풍 수습"})

        self.assertEqual(result["status"], "publishable")
        self.assertTrue(result["attempted_regenerate"])
        regenerate_publish_source.assert_called_once()

    @patch("core.quality_gate_orchestrator.regenerate_publish_source")
    def test_evaluate_quality_gate_does_not_regenerate_non_regenerateable_hard_fail(self, regenerate_publish_source):
        result = evaluate_quality_gate(_valid_source(content="# 99화. 완전히 다른 번호\\n\\n짧음"))
        self.assertEqual(result["status"], "hard_fail")
        regenerate_publish_source.assert_not_called()

    @patch("core.quality_gate_orchestrator.regenerate_publish_source")
    @patch("core.quality_gate_orchestrator.evaluate_publish_critic")
    def test_evaluate_quality_gate_hard_fails_when_regenerated_source_still_fails(
        self,
        evaluate_publish_critic,
        regenerate_publish_source,
    ):
        evaluate_publish_critic.return_value = {
            "status": "blocked",
            "summary": "objective drift",
            "issues": ["episode objective missing"],
            "model": "gemini-2.5-flash",
            "cost": {"mode": "single_pass"},
            "raw_excerpt": "",
        }
        regenerate_publish_source.return_value = {
            "status": "applied",
            "reason": "",
            "title": "12화. 계약의 대가",
            "content": "# 12화. 계약의 대가\\n\\n재생성했지만 여전히 문제가 있는 본문",
            "regeneration_summary": "still weak",
        }

        result = evaluate_quality_gate(_valid_source(), episode_plan={"episode_objective": "계약 후폭풍 수습"})

        self.assertEqual(result["status"], "hard_fail")
        self.assertTrue(result["attempted_regenerate"])
```

- [ ] **Step 2: Run the focused orchestrator tests and confirm failure**

Run: `python3 -m unittest tests.test_quality_gate_orchestrator -v`

Expected: FAIL because regenerate support does not exist in the orchestrator yet.

- [ ] **Step 3: Implement regenerate-once orchestration**

Modify `core/quality_gate_orchestrator.py` to:

- import `regenerate_publish_source`
- add:
  - `_is_regenerateable_hard_fail(...)`
  - `_merge_regenerated_source(...)`
  - `_build_regeneration_summary(...)`
- extend result payloads with:
  - `attempted_regenerate`
  - `regeneration_summary`
- accept injectable argument:

```python
def evaluate_quality_gate(
    source_payload: dict,
    *,
    episode_plan: dict | None = None,
    repair_enabled: bool = True,
    regenerate_enabled: bool = True,
    regenerate_fn=None,
) -> dict:
```

Behavior:

1. run current cheap gates and optional repair exactly as today
2. if final candidate becomes publishable -> run critic
3. if critic blocks, classify as regenerateable
4. if regenerateable and regeneration enabled:
   - call `regenerate_fn or regenerate_publish_source(...)`
   - merge regenerated `title/content`
   - re-run cheap gates and critic once
5. if regenerated candidate passes -> return `publishable`
6. otherwise -> return final `hard_fail`

Do not regenerate:

- number mismatch
- empty content
- auxiliary marker contamination that should stay a cheap-gate failure
- `critic_unavailable`

- [ ] **Step 4: Re-run the focused orchestrator tests**

Run: `python3 -m unittest tests.test_quality_gate_orchestrator -v`

Expected: PASS

- [ ] **Step 5: Commit chunk 2**

```bash
git add core/quality_gate_orchestrator.py tests/test_quality_gate_orchestrator.py
git commit -m "feat: add regenerate-once quality orchestration"
```

## Chunk 3: Prove runtime stays coordinator-only

### Task 3: Add regenerate-aware runtime tests

**Files:**
- Modify: `tests/test_publishing_runtime.py`
- Modify: `core/publishing_runtime.py`

- [ ] **Step 1: Add failing runtime regression tests**

Add tests like:

```python
    def test_tick_uses_regenerated_final_source_for_executor_payload(self):
        quality_report = {
            "status": "publishable",
            "attempted_repair": False,
            "attempted_regenerate": True,
            "final_source": {
                "title": "12화. 계약의 대가",
                "content": "# 12화. 계약의 대가\\n\\n재생성된 최종 본문",
            },
            "gate_reports": {"regenerated": {"critic": {"status": "passed"}}},
            "errors": [],
            "repair_summary": {"status": "not_needed", "reason": ""},
            "regeneration_summary": {"status": "applied", "reason": ""},
        }
```

Assertions:

- executor receives regenerated `source_override`
- `quality_report.json` preserves `attempted_regenerate`
- runtime does not add new retry logic outside the orchestrator

- [ ] **Step 2: Run focused runtime tests and confirm failure**

Run: `python3 -m unittest tests.test_publishing_runtime -v`

Expected: FAIL because current expectations do not cover regenerate-aware report details.

- [ ] **Step 3: Make the minimal runtime adjustments**

Only if needed, update `core/publishing_runtime.py` so it:

- continues to persist the full `quality_report`
- continues to derive `source_override` only from `final_source`
- does not add runtime-owned regenerate policy

Prefer test updates over production changes if runtime already behaves correctly.

- [ ] **Step 4: Re-run the focused runtime tests**

Run: `python3 -m unittest tests.test_publishing_runtime -v`

Expected: PASS

- [ ] **Step 5: Commit chunk 3**

```bash
git add core/publishing_runtime.py tests/test_publishing_runtime.py
git commit -m "test: cover regenerate-aware publishing runtime"
```

## Chunk 4: Full regression and verification

### Task 4: Run the complete verification set

**Files:**
- Verify only:
  - `core/publishing_regenerate.py`
  - `core/quality_gate_orchestrator.py`
  - `core/publishing_runtime.py`
  - `tests/test_publishing_regenerate.py`
  - `tests/test_quality_gate_orchestrator.py`
  - `tests/test_publishing_runtime.py`

- [ ] **Step 1: Run focused regressions**

Run:

```bash
python3 -m unittest \
  tests.test_publishing_regenerate \
  tests.test_quality_gate_orchestrator \
  tests.test_publishing_runtime -v
```

Expected: PASS

- [ ] **Step 2: Run broader publish-control regressions**

Run:

```bash
python3 -m unittest \
  tests.test_generator_planning \
  tests.test_episode_planner \
  tests.test_publishing_quality \
  tests.test_publishing_structure \
  tests.test_publishing_critic \
  tests.test_publish_packager \
  tests.test_platform_client_base \
  tests.test_munpia_client \
  tests.test_novelpia_client \
  tests.test_publishing_executor \
  tests.test_release_policy_engine \
  tests.test_publishing_policy \
  tests.test_publishing_incidents \
  tests.test_publishing_canon \
  tests.test_publishing_runtime \
  tests.test_publishing_ui -v
```

Expected: PASS

- [ ] **Step 3: Run compile and diff checks**

Run:

```bash
python3 -m py_compile \
  core/publishing_regenerate.py \
  core/quality_gate_orchestrator.py \
  core/publishing_runtime.py \
  tests/test_publishing_regenerate.py \
  tests/test_quality_gate_orchestrator.py \
  tests/test_publishing_runtime.py

git diff --check -- \
  core/publishing_regenerate.py \
  core/quality_gate_orchestrator.py \
  core/publishing_runtime.py \
  tests/test_publishing_regenerate.py \
  tests/test_quality_gate_orchestrator.py \
  tests/test_publishing_runtime.py \
  docs/superpowers/specs/2026-03-16-quality-gate-regenerate-once-v1-design.md \
  docs/superpowers/plans/2026-03-16-quality-gate-regenerate-once-v1.md
```

Expected: both commands succeed with no output.

- [ ] **Step 4: Commit verification-safe finishing changes**

```bash
git add \
  core/publishing_regenerate.py \
  core/quality_gate_orchestrator.py \
  core/publishing_runtime.py \
  tests/test_publishing_regenerate.py \
  tests/test_quality_gate_orchestrator.py \
  tests/test_publishing_runtime.py \
  docs/superpowers/plans/2026-03-16-quality-gate-regenerate-once-v1.md
git commit -m "feat: add regenerate-once publish quality retry"
```

## Notes for the implementing agent

- Keep the same `episode_plan`; do not regenerate planning.
- Do not let `publishing_runtime.py` decide when regeneration happens.
- Keep bounded failure behavior: one repair, one regeneration, then stop.
- Prefer small helper functions over growing `quality_gate_orchestrator.py` into another god file.
- Preserve existing runtime-facing statuses: `publishable` and `hard_fail`.
