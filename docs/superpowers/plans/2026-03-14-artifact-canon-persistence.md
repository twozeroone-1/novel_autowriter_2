# Artifact Canon Persistence Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist final-episode Canon candidates into episode artifacts, stop non-episode markdown files from polluting the manifest, and let publishing reuse stored Canon candidates before extractor fallback.

**Architecture:** Extend `EpisodeArtifactStore` with a dedicated `canon_updates` directory and path-based manifest metadata, split `Generator` into general markdown saves vs canonical episode saves, and make `PublishingRuntime` read stored Canon candidates before calling the extractor again.

**Tech Stack:** Python, unittest, existing `EpisodeArtifactStore`, `Generator`, `Automator`, `PublishingRuntime`

---

## Chunk 1: Episode artifact store support

### Task 1: Add Canon candidate persistence to `EpisodeArtifactStore`

**Files:**
- Modify: `core/episode_artifact_store.py`
- Modify: `tests/test_episode_artifact_store.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_create_draft_records_canon_update_path_in_manifest():
    ...

def test_save_and_load_canon_update_round_trip():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_episode_artifact_store -v`
Expected: FAIL because the store does not expose Canon candidate persistence yet.

- [ ] **Step 3: Write the minimal implementation**

In `core/episode_artifact_store.py`:

- add `canon_updates_dir`
- add manifest field `canon_update_path`
- implement `save_canon_update()` and `load_canon_update()`
- normalize payload with existing Canon candidate helper before writing

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_episode_artifact_store -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/episode_artifact_store.py tests/test_episode_artifact_store.py
git commit -m "feat: persist canon candidates in episode artifacts"
```

## Chunk 2: Canonical episode save boundary

### Task 2: Stop generic markdown saves from creating episode artifacts

**Files:**
- Modify: `core/generator.py`
- Modify: `tests/test_generator_storage.py`
- Modify: `tests/test_automator.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_save_markdown_document_does_not_create_episode_artifact_by_default():
    ...

def test_run_single_cycle_persists_canon_update_for_saved_episode():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_generator_storage tests.test_automator -v`
Expected: FAIL because generic markdown saves still create artifacts and Canon candidates are not persisted to artifact storage.

- [ ] **Step 3: Write the minimal implementation**

In `core/generator.py`:

- add an internal save helper that can optionally create episode artifacts
- make `save_markdown_document()` default to non-artifact behavior
- add a canonical episode save path that returns episode metadata for final chapters
- keep `save_chapter()` backward-compatible by returning the path string

In `core/automator.py`:

- use the canonical episode save path
- persist `canon_update` with `artifact_store.save_canon_update(episode_id, payload)` when extraction succeeds

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_generator_storage tests.test_automator -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/generator.py core/automator.py tests/test_generator_storage.py tests/test_automator.py
git commit -m "feat: persist final episode canon artifacts"
```

## Chunk 3: Publish-time reuse of stored Canon candidates

### Task 3: Prefer stored artifact candidates before extractor fallback

**Files:**
- Modify: `core/chapter_source.py`
- Modify: `core/publishing_runtime.py`
- Modify: `tests/test_chapter_source.py`
- Modify: `tests/test_publishing_runtime.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:

```python
def test_load_chapter_source_includes_stored_canon_update_for_episode_artifact():
    ...

def test_tick_prefers_artifact_canon_update_before_extractor_fallback():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_chapter_source tests.test_publishing_runtime -v`
Expected: FAIL because stored artifact Canon candidates are not surfaced or consumed yet.

- [ ] **Step 3: Write the minimal implementation**

In `core/chapter_source.py`:

- include `canon_update` in the returned payload when an episode artifact exists and a stored candidate file is present

In `core/publishing_runtime.py`:

- update Canon candidate resolution order to:
  1. result
  2. job
  3. source payload stored artifact
  4. extractor fallback

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_chapter_source tests.test_publishing_runtime -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/chapter_source.py core/publishing_runtime.py tests/test_chapter_source.py tests/test_publishing_runtime.py
git commit -m "feat: reuse stored canon artifacts during publish"
```

## Chunk 4: Verification

### Task 4: Run focused and broader regressions

**Files:**
- Test: `tests/test_episode_artifact_store.py`
- Test: `tests/test_generator_storage.py`
- Test: `tests/test_automator.py`
- Test: `tests/test_chapter_source.py`
- Test: `tests/test_publishing_runtime.py`

- [ ] **Step 1: Run focused artifact and Canon tests**

Run: `python3 -m unittest tests.test_episode_artifact_store tests.test_generator_storage tests.test_automator tests.test_chapter_source tests.test_publishing_runtime -v`
Expected: PASS

- [ ] **Step 2: Run broader origin-pipeline regressions**

Run: `python3 -m unittest tests.test_story_bible_store tests.test_canon_store tests.test_release_policy_store tests.test_episode_artifact_store tests.test_run_snapshot_store tests.test_origin_quality tests.test_context_manager tests.test_generator_storage tests.test_chapter_source tests.test_automation_store tests.test_automation_runtime tests.test_automation_ui tests.test_diagnostics_ui tests.test_automator tests.test_canon_extractor tests.test_publishing_executor tests.test_publishing_runtime -v`
Expected: PASS

- [ ] **Step 3: Run syntax verification**

Run: `python3 -m py_compile core/episode_artifact_store.py core/generator.py core/automator.py core/chapter_source.py core/publishing_runtime.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-03-14-artifact-canon-persistence-design.md docs/superpowers/plans/2026-03-14-artifact-canon-persistence.md
git commit -m "docs: add artifact canon persistence plan"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-14-artifact-canon-persistence.md`. Ready to execute?
