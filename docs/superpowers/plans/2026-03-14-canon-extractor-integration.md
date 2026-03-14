# Canon Extractor Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared Canon extractor so finalized episode text produces structured `canon_update` candidates that flow through automation results and can be consumed by the publishing runtime.

**Architecture:** Add a focused `core/canon_extractor.py` module that owns prompt construction, JSON parsing, and normalization to CanonStore shape. Keep `Generator` as a thin wrapper, extend `Automator` to include `canon_update` and `canon_update_error`, and let `PublishingRuntime` consume a provided candidate while preserving temporary timeline fallback compatibility.

**Tech Stack:** Python, unittest, existing `generate_text`, `CanonStore`, `Automator`, `PublishingRuntime`

---

## Chunk 1: Canon extractor foundation

### Task 1: Add extractor tests and implementation

**Files:**
- Create: `core/canon_extractor.py`
- Create: `tests/test_canon_extractor.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_extract_canon_update_parses_json_object_from_llm_response():
    ...

def test_extract_canon_update_normalizes_partial_payload():
    ...

def test_extract_canon_update_rejects_missing_json_payload():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_canon_extractor -v`
Expected: FAIL because the module does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Implement `core/canon_extractor.py` with:

- `build_canon_extraction_prompt(chapter_content: str) -> str`
- `extract_canon_update(chapter_content: str, *, project_name: str | None = None) -> dict`
- reuse `_extract_first_json_value(..., expected_type=dict)`
- normalize to `people/resources/hooks/timeline`
- raise `ValueError` when no JSON object can be extracted

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_canon_extractor -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/canon_extractor.py tests/test_canon_extractor.py
git commit -m "feat: add canon extractor foundation"
```

## Chunk 2: Automator integration

### Task 2: Emit `canon_update` from finalized chapter flow

**Files:**
- Modify: `core/generator.py`
- Modify: `core/automator.py`
- Modify: `tests/test_automator.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_run_single_cycle_includes_canon_update_when_extraction_succeeds():
    ...

def test_run_single_cycle_keeps_canon_update_error_without_failing_pipeline():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_automator -v`
Expected: FAIL because `Automator.run_single_cycle()` does not yet attach Canon extraction results.

- [ ] **Step 3: Write the minimal implementation**

In `core/generator.py`, add:

```python
def build_canon_update_candidate(self, chapter_content: str) -> dict:
    ...
```

In `core/automator.py`, after saving the revised chapter:

- call the generator wrapper
- store `result["canon_update"]` on success
- store `result["canon_update_error"]` on failure
- keep failure isolated from the rest of the cycle

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_automator -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/generator.py core/automator.py tests/test_automator.py
git commit -m "feat: emit canon candidates from automator"
```

## Chunk 3: Publishing runtime consumption

### Task 3: Apply provided canon candidates on publish success

**Files:**
- Modify: `core/publishing_runtime.py`
- Modify: `tests/test_publishing_runtime.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_tick_applies_canon_update_payload_when_publish_succeeds():
    ...

def test_tick_keeps_timeline_fallback_when_canon_update_missing():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_runtime.TestPublishingRuntime.test_tick_applies_canon_update_payload_when_publish_succeeds tests.test_publishing_runtime.TestPublishingRuntime.test_tick_keeps_timeline_fallback_when_canon_update_missing -v`
Expected: FAIL because `PublishingRuntime` only writes timeline today.

- [ ] **Step 3: Write the minimal implementation**

In `core/publishing_runtime.py`:

- add a helper that reads a `canon_update` payload from publish result first, then from the job
- normalize it with the shared candidate normalizer
- if non-empty, merge it into CanonStore and ensure the current `episode_id` is present in timeline
- otherwise keep the existing timeline-only fallback

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_publishing_runtime.TestPublishingRuntime.test_tick_applies_canon_update_payload_when_publish_succeeds tests.test_publishing_runtime.TestPublishingRuntime.test_tick_keeps_timeline_fallback_when_canon_update_missing -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/publishing_runtime.py tests/test_publishing_runtime.py
git commit -m "feat: apply canon candidates on publish success"
```

## Chunk 4: Verification

### Task 4: Run focused and broader regressions

**Files:**
- Test: `tests/test_canon_extractor.py`
- Test: `tests/test_automator.py`
- Test: `tests/test_automation_runtime.py`
- Test: `tests/test_publishing_runtime.py`

- [ ] **Step 1: Run focused Canon-path tests**

Run: `python3 -m unittest tests.test_canon_extractor tests.test_automator tests.test_automation_runtime tests.test_publishing_runtime -v`
Expected: PASS

- [ ] **Step 2: Run broader origin-pipeline regressions**

Run: `python3 -m unittest tests.test_story_bible_store tests.test_canon_store tests.test_release_policy_store tests.test_episode_artifact_store tests.test_run_snapshot_store tests.test_origin_quality tests.test_context_manager tests.test_generator_storage tests.test_chapter_source tests.test_automation_store tests.test_automation_runtime tests.test_automation_ui tests.test_diagnostics_ui tests.test_automator tests.test_canon_extractor tests.test_publishing_executor tests.test_publishing_runtime -v`
Expected: PASS

- [ ] **Step 3: Run syntax verification**

Run: `python3 -m py_compile core/canon_extractor.py core/generator.py core/automator.py core/publishing_runtime.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-03-14-canon-extractor-integration-design.md docs/superpowers/plans/2026-03-14-canon-extractor-integration.md
git commit -m "docs: add canon extractor integration design"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-14-canon-extractor-integration.md`. Ready to execute?
