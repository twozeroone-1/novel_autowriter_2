# Publish Canon Gating Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce that Canon DB updates happen only when structured extraction succeeds after a successful publish, with explicit runtime evidence for applied or skipped Canon updates.

**Architecture:** Keep `PublishingRuntime` as the only place that mutates `CanonStore` after publication. Resolve Canon candidates from `result` or `job` first, fall back to `CanonExtractor` on the published source content when needed, and record a structured `canon_update` report in run snapshots and publishing history.

**Tech Stack:** Python, unittest, existing `PublishingRuntime`, `CanonStore`, `CanonExtractor`, `RunSnapshotStore`

---

## Chunk 1: Tighten publish-time Canon gating

### Task 1: Add failing tests for extractor fallback and strict gating

**Files:**
- Modify: `tests/test_publishing_runtime.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_tick_uses_extractor_fallback_when_publish_result_has_no_canon_update():
    ...

def test_tick_skips_canon_update_when_extractor_fails():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_runtime.TestPublishingRuntime.test_tick_uses_extractor_fallback_when_publish_result_has_no_canon_update tests.test_publishing_runtime.TestPublishingRuntime.test_tick_skips_canon_update_when_extractor_fails -v`
Expected: FAIL because `PublishingRuntime` still falls back to timeline-only Canon updates.

- [ ] **Step 3: Write the minimal implementation**

In `core/publishing_runtime.py`:

- add a helper that resolves Canon candidate from `result`, then `job`, then extractor fallback on `source_payload["content"]`
- remove the timeline-only Canon DB fallback
- return a structured report:

```python
{
    "status": "applied" | "skipped" | "failed",
    "source": "result" | "job" | "extractor" | "none",
    "candidate": {...},
    "error": "...",
}
```

- only call `CanonStore.apply_state_update()` when the report status is `applied`

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_publishing_runtime.TestPublishingRuntime.test_tick_uses_extractor_fallback_when_publish_result_has_no_canon_update tests.test_publishing_runtime.TestPublishingRuntime.test_tick_skips_canon_update_when_extractor_fails -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/publishing_runtime.py tests/test_publishing_runtime.py
git commit -m "feat: enforce publish-time canon gating"
```

## Chunk 2: Persist Canon update evidence

### Task 2: Record Canon update reports in snapshots and publishing history

**Files:**
- Modify: `core/publishing_runtime.py`
- Modify: `tests/test_publishing_runtime.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_tick_writes_canon_update_snapshot_and_history_record():
    ...
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `python3 -m unittest tests.test_publishing_runtime.TestPublishingRuntime.test_tick_writes_canon_update_snapshot_and_history_record -v`
Expected: FAIL because no explicit `canon_update.json` snapshot or history field exists yet.

- [ ] **Step 3: Write the minimal implementation**

In `core/publishing_runtime.py`:

- write `canon_update.json` into the run snapshot directory
- include the same payload under `history_record["canon_update"]`
- append Canon events with `canon_update_status` and `canon_update_source`

- [ ] **Step 4: Run the targeted test to verify it passes**

Run: `python3 -m unittest tests.test_publishing_runtime.TestPublishingRuntime.test_tick_writes_canon_update_snapshot_and_history_record -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/publishing_runtime.py tests/test_publishing_runtime.py
git commit -m "feat: record publish canon update evidence"
```

## Chunk 3: Verification

### Task 3: Run focused and broader regression verification

**Files:**
- Test: `tests/test_publishing_runtime.py`
- Test: `tests/test_canon_extractor.py`
- Test: `tests/test_automator.py`

- [ ] **Step 1: Run focused publish/Canon tests**

Run: `python3 -m unittest tests.test_publishing_runtime tests.test_canon_extractor tests.test_automator -v`
Expected: PASS

- [ ] **Step 2: Run broader origin-pipeline regressions**

Run: `python3 -m unittest tests.test_story_bible_store tests.test_canon_store tests.test_release_policy_store tests.test_episode_artifact_store tests.test_run_snapshot_store tests.test_origin_quality tests.test_context_manager tests.test_generator_storage tests.test_chapter_source tests.test_automation_store tests.test_automation_runtime tests.test_automation_ui tests.test_diagnostics_ui tests.test_automator tests.test_canon_extractor tests.test_publishing_executor tests.test_publishing_runtime -v`
Expected: PASS

- [ ] **Step 3: Run syntax verification**

Run: `python3 -m py_compile core/publishing_runtime.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-03-14-publish-canon-gating-design.md docs/superpowers/plans/2026-03-14-publish-canon-gating.md
git commit -m "docs: add publish canon gating plan"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-14-publish-canon-gating.md`. Ready to execute?
