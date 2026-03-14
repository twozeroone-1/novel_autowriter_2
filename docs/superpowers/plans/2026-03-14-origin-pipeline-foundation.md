# Origin Pipeline Foundation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the first executable phase of the fully automated serialization design by adding structured source-of-truth stores, episode artifact lifecycle storage, minimal origin quality gates, and a publication-success path that updates Canon only after verified origin publication.

**Architecture:** Build new foundation modules alongside the existing app instead of rewriting everything at once. The new phase introduces `Story Bible`, `Canon`, `Release Policy`, `episode artifacts`, and `run snapshots` as explicit stores, then threads a small amount of metadata through generator and publishing runtime so Korean origin publication becomes deterministic and auditable without yet implementing the full multi-model planner/critic system.

**Tech Stack:** Python 3, unittest, existing JSON/JSONL project stores, Streamlit-compatible project structure

---

## Scope Note

This plan is intentionally narrower than the full design spec. It implements the minimum reliable foundation for:

- structured source of truth
- episode draft/publishable/published storage
- run snapshots
- low-cost rule-based gating
- Canon updates only after successful origin publication

This plan does **not** implement yet:

- critic-model based quality review
- marketing generation
- locale pipeline execution
- overseas platform adapters
- full planner-driven episode orchestration

Those belong to later plans once this foundation is stable.

## File Map

- Create: `core/story_bible_store.py`
  - Persist structured Story Bible sections under `data/projects/<project>/story_bible/`.
- Create: `core/canon_store.py`
  - Persist append-only canon events and current canon state under `data/projects/<project>/canon/`.
- Create: `core/release_policy_store.py`
  - Persist platform-aware release policy rules separately from existing automation config.
- Create: `core/episode_artifact_store.py`
  - Manage `episodes/drafts`, `episodes/publishable`, `episodes/published`, and episode manifests.
- Create: `core/run_snapshot_store.py`
  - Persist per-run inputs, outputs, quality reports, and publication results under `runs/<run_id>/`.
- Create: `core/origin_quality.py`
  - Run low-cost rule-based checks for title, episode number, length, forbidden markers, and repeated-line patterns.
- Modify: `core/generator.py`
  - Save draft artifacts with deterministic metadata through `EpisodeArtifactStore` while preserving current markdown output behavior.
- Modify: `core/chapter_source.py`
  - Load published/publishable episode artifacts by manifest when available, falling back to legacy chapter paths.
- Modify: `core/publishing_executor.py`
  - Carry episode metadata through publish execution and return artifact-aware source metadata.
- Modify: `core/publishing_runtime.py`
  - Enforce minimal origin quality gating before publication, write run snapshots, and update Canon only after verified success.
- Create: `tests/test_story_bible_store.py`
  - Cover default structure, save/load normalization, and text export helpers.
- Create: `tests/test_canon_store.py`
  - Cover append-only canon events, current-state merge behavior, and snapshot loading.
- Create: `tests/test_release_policy_store.py`
  - Cover default policy payloads and platform override loading.
- Create: `tests/test_episode_artifact_store.py`
  - Cover deterministic episode IDs, artifact paths, manifest updates, and promotion from draft to publishable/published.
- Create: `tests/test_run_snapshot_store.py`
  - Cover run directory layout and snapshot writes.
- Create: `tests/test_origin_quality.py`
  - Cover failing and passing rule-based quality reports.
- Modify: `tests/test_generator_storage.py`
  - Cover new draft artifact writes while preserving filename sanitization.
- Modify: `tests/test_chapter_source.py`
  - Cover artifact-first loading and legacy fallback.
- Modify: `tests/test_publishing_executor.py`
  - Cover executor returning artifact-aware source metadata.
- Modify: `tests/test_publishing_runtime.py`
  - Cover gate failure stop, snapshot writing, and Canon update only on success.

## Data Layout Target

This phase should converge on the following project layout:

```text
data/projects/<project>/
  story_bible/
    story_bible.json
  canon/
    current_state.json
    events.jsonl
    snapshots/
      ep_001.json
  release_policy/
    policy.json
  episodes/
    manifests.json
    drafts/
      ep_001.md
    publishable/
      ep_001.md
    published/
      ep_001.md
  runs/
    run_20260314_0001/
      input_snapshot.json
      quality_report.json
      publish_result.json
```

Legacy `chapters/*.md` may continue to exist for compatibility, but the new stores become the authoritative origin pipeline data.

## Chunk 1: Source of Truth Stores

### Task 1: Add failing tests for Story Bible store

**Files:**
- Create: `tests/test_story_bible_store.py`
- Create: `core/story_bible_store.py`

- [ ] **Step 1: Inspect existing store conventions**

Run:

```bash
python3 -m unittest tests.test_automation_store tests.test_publishing_store -v
```

Expected: confirm existing JSON store patterns and temp-directory patching style.

- [ ] **Step 2: Write the failing Story Bible store tests**

```python
def test_load_story_bible_returns_default_sections():
    store = StoryBibleStore(project_name="sample")
    story_bible = store.load()

    assert story_bible["worldview"]
    assert story_bible["style_guide"]
    assert story_bible["fixed_rules"]
    assert story_bible["author_intent"] == ""

def test_save_story_bible_normalizes_missing_sections():
    ...

def test_export_prompt_sections_formats_story_bible_text():
    ...
```

- [ ] **Step 3: Run the focused Story Bible tests**

Run:

```bash
python3 -m unittest tests.test_story_bible_store -v
```

Expected: FAIL because `StoryBibleStore` does not exist yet.

- [ ] **Step 4: Implement the minimal Story Bible store**

Create `core/story_bible_store.py` with:
- default section payload
- project directory/path helpers
- `load()`, `save()`
- prompt export helpers for worldview/style/fixed-rules text blocks

- [ ] **Step 5: Re-run the focused Story Bible tests**

Run:

```bash
python3 -m unittest tests.test_story_bible_store -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/story_bible_store.py tests/test_story_bible_store.py
git commit -m "feat: add story bible store"
```

### Task 2: Add failing tests for Canon store

**Files:**
- Create: `tests/test_canon_store.py`
- Create: `core/canon_store.py`

- [ ] **Step 1: Write the failing Canon store tests**

```python
def test_load_current_state_returns_default_structure():
    ...

def test_append_event_persists_jsonl_record():
    ...

def test_apply_state_update_merges_people_resources_and_hooks():
    ...

def test_write_snapshot_creates_episode_snapshot_file():
    ...
```

- [ ] **Step 2: Run the focused Canon tests**

Run:

```bash
python3 -m unittest tests.test_canon_store -v
```

Expected: FAIL because `CanonStore` does not exist yet.

- [ ] **Step 3: Implement the minimal Canon store**

Include:
- `current_state.json` loader/saver
- append-only `events.jsonl`
- simple merge helper for structured state updates
- `write_snapshot(episode_id, state)` helper

- [ ] **Step 4: Re-run the focused Canon tests**

Run:

```bash
python3 -m unittest tests.test_canon_store -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/canon_store.py tests/test_canon_store.py
git commit -m "feat: add canon store"
```

### Task 3: Add failing tests for release policy storage

**Files:**
- Create: `tests/test_release_policy_store.py`
- Create: `core/release_policy_store.py`

- [ ] **Step 1: Write the failing release policy tests**

```python
def test_load_policy_returns_platform_defaults():
    ...

def test_save_policy_round_trips_platform_overrides():
    ...
```

- [ ] **Step 2: Run the focused release policy tests**

Run:

```bash
python3 -m unittest tests.test_release_policy_store -v
```

Expected: FAIL because `ReleasePolicyStore` does not exist yet.

- [ ] **Step 3: Implement the minimal release policy store**

Store:
- global defaults
- per-platform overrides
- burst policy settings
- cooldown thresholds

- [ ] **Step 4: Re-run the focused release policy tests**

Run:

```bash
python3 -m unittest tests.test_release_policy_store -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/release_policy_store.py tests/test_release_policy_store.py
git commit -m "feat: add release policy store"
```

## Chunk 2: Episode Artifact Lifecycle

### Task 4: Add failing tests for episode artifact storage and promotion

**Files:**
- Create: `tests/test_episode_artifact_store.py`
- Create: `core/episode_artifact_store.py`

- [ ] **Step 1: Write failing artifact store tests**

```python
def test_create_draft_assigns_episode_id_and_manifest_entry():
    ...

def test_promote_draft_to_publishable_copies_expected_artifact():
    ...

def test_mark_published_writes_published_artifact_and_manifest_status():
    ...

def test_existing_episode_number_is_reused_for_same_episode_id():
    ...
```

- [ ] **Step 2: Run the focused artifact store tests**

Run:

```bash
python3 -m unittest tests.test_episode_artifact_store -v
```

Expected: FAIL because `EpisodeArtifactStore` does not exist yet.

- [ ] **Step 3: Implement the minimal artifact store**

Include:
- manifest file loader/saver
- draft/publishable/published paths
- deterministic `episode_id` and sequence handling
- promotion helpers

- [ ] **Step 4: Re-run the focused artifact store tests**

Run:

```bash
python3 -m unittest tests.test_episode_artifact_store -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/episode_artifact_store.py tests/test_episode_artifact_store.py
git commit -m "feat: add episode artifact lifecycle store"
```

### Task 5: Add failing tests for run snapshot storage

**Files:**
- Create: `tests/test_run_snapshot_store.py`
- Create: `core/run_snapshot_store.py`

- [ ] **Step 1: Write failing run snapshot tests**

```python
def test_create_run_directory_and_write_named_snapshots():
    ...

def test_snapshot_store_preserves_serializable_payloads():
    ...
```

- [ ] **Step 2: Run the focused run snapshot tests**

Run:

```bash
python3 -m unittest tests.test_run_snapshot_store -v
```

Expected: FAIL because `RunSnapshotStore` does not exist yet.

- [ ] **Step 3: Implement the minimal run snapshot store**

Include:
- run ID creation helper
- `write_json_snapshot`
- `write_text_snapshot`
- run directory path resolution

- [ ] **Step 4: Re-run the focused run snapshot tests**

Run:

```bash
python3 -m unittest tests.test_run_snapshot_store -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/run_snapshot_store.py tests/test_run_snapshot_store.py
git commit -m "feat: add run snapshot store"
```

## Chunk 3: Low-Cost Origin Quality Gates

### Task 6: Add failing tests for origin quality reports

**Files:**
- Create: `tests/test_origin_quality.py`
- Create: `core/origin_quality.py`

- [ ] **Step 1: Write failing quality gate tests**

```python
def test_validate_origin_draft_rejects_missing_episode_number():
    ...

def test_validate_origin_draft_rejects_too_short_content():
    ...

def test_validate_origin_draft_rejects_repeated_line_spam():
    ...

def test_validate_origin_draft_passes_for_well_formed_episode():
    ...
```

- [ ] **Step 2: Run the focused origin quality tests**

Run:

```bash
python3 -m unittest tests.test_origin_quality -v
```

Expected: FAIL because `validate_origin_draft` does not exist yet.

- [ ] **Step 3: Implement the minimal rule-based quality checker**

Checks should include:
- episode title/number presence
- minimum body length
- blocked placeholders such as `TODO`, `초안`, `검수리포트`
- repeated-line threshold
- obvious empty-heading cases

- [ ] **Step 4: Re-run the focused origin quality tests**

Run:

```bash
python3 -m unittest tests.test_origin_quality -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/origin_quality.py tests/test_origin_quality.py
git commit -m "feat: add origin quality gates"
```

## Chunk 4: Generator and Publication Integration

### Task 7: Add failing tests for generator draft artifact writes

**Files:**
- Modify: `tests/test_generator_storage.py`
- Modify: `core/generator.py`

- [ ] **Step 1: Add a failing test for draft artifact creation alongside legacy markdown**

```python
def test_save_chapter_writes_episode_draft_artifact():
    ...
```

- [ ] **Step 2: Run the focused generator storage tests**

Run:

```bash
python3 -m unittest tests.test_generator_storage -v
```

Expected: FAIL because generator does not yet write draft artifacts.

- [ ] **Step 3: Implement minimal generator integration**

Keep current chapter markdown output, but also:
- create or update episode manifest entry
- write a draft artifact to `episodes/drafts`
- return enough metadata for later pipeline use

- [ ] **Step 4: Re-run the focused generator storage tests**

Run:

```bash
python3 -m unittest tests.test_generator_storage -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/generator.py tests/test_generator_storage.py
git commit -m "feat: persist draft episode artifacts"
```

### Task 8: Add failing tests for artifact-aware source loading

**Files:**
- Modify: `tests/test_chapter_source.py`
- Modify: `core/chapter_source.py`

- [ ] **Step 1: Add a failing artifact-first loading test**

```python
def test_load_chapter_source_prefers_publishable_episode_artifact():
    ...
```

- [ ] **Step 2: Add a failing legacy fallback test**

```python
def test_load_chapter_source_falls_back_to_legacy_chapter_path():
    ...
```

- [ ] **Step 3: Run the focused chapter source tests**

Run:

```bash
python3 -m unittest tests.test_chapter_source -v
```

Expected: FAIL because artifact-first loading is not implemented yet.

- [ ] **Step 4: Implement minimal artifact-aware source loading**

Behavior:
- if a manifest-backed publishable/published artifact exists, use it
- otherwise fall back to the existing file-path logic

- [ ] **Step 5: Re-run the focused chapter source tests**

Run:

```bash
python3 -m unittest tests.test_chapter_source -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/chapter_source.py tests/test_chapter_source.py
git commit -m "feat: load episode artifacts before legacy chapters"
```

### Task 9: Add failing tests for publishing runtime gating, snapshots, and Canon updates

**Files:**
- Modify: `tests/test_publishing_executor.py`
- Modify: `tests/test_publishing_runtime.py`
- Modify: `core/publishing_executor.py`
- Modify: `core/publishing_runtime.py`

- [ ] **Step 1: Add failing runtime tests**

```python
def test_runtime_blocks_publication_when_origin_quality_fails():
    ...

def test_runtime_writes_run_snapshots_for_attempted_publication():
    ...

def test_runtime_updates_canon_only_after_successful_origin_publication():
    ...
```

- [ ] **Step 2: Run the focused publishing tests**

Run:

```bash
python3 -m unittest tests.test_publishing_executor tests.test_publishing_runtime -v
```

Expected: FAIL because gating/snapshots/Canon updates are not implemented yet.

- [ ] **Step 3: Implement minimal publishing integration**

Add:
- pre-publication `validate_origin_draft` call
- run snapshot writes for input, quality report, and publish result
- Canon event append + current-state update + snapshot write only when overall status is `done`

Keep platform client behavior unchanged beyond carrying artifact metadata through the result payload.

- [ ] **Step 4: Re-run the focused publishing tests**

Run:

```bash
python3 -m unittest tests.test_publishing_executor tests.test_publishing_runtime -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/publishing_executor.py core/publishing_runtime.py tests/test_publishing_executor.py tests/test_publishing_runtime.py
git commit -m "feat: gate origin publication and update canon on success"
```

## Chunk 5: Verification

### Task 10: Verify the phase-1 origin pipeline foundation

**Files:**
- Verify only

- [ ] **Step 1: Run the new and updated targeted test set**

Run:

```bash
python3 -m unittest \
  tests.test_story_bible_store \
  tests.test_canon_store \
  tests.test_release_policy_store \
  tests.test_episode_artifact_store \
  tests.test_run_snapshot_store \
  tests.test_origin_quality \
  tests.test_generator_storage \
  tests.test_chapter_source \
  tests.test_publishing_executor \
  tests.test_publishing_runtime \
  -v
```

Expected: PASS.

- [ ] **Step 2: Re-run compatibility tests around adjacent existing behavior**

Run:

```bash
python3 -m unittest \
  tests.test_context_manager \
  tests.test_automation_store \
  tests.test_publishing_store \
  tests.test_publishing_ui \
  -v
```

Expected: PASS.

- [ ] **Step 3: Run lightweight syntax verification**

Run:

```bash
python3 -m py_compile \
  core/story_bible_store.py \
  core/canon_store.py \
  core/release_policy_store.py \
  core/episode_artifact_store.py \
  core/run_snapshot_store.py \
  core/origin_quality.py \
  core/generator.py \
  core/chapter_source.py \
  core/publishing_executor.py \
  core/publishing_runtime.py
```

Expected: no output.

- [ ] **Step 4: Manual smoke check**

Verify in the app or direct store inspection:
- saving a chapter creates a draft artifact and manifest entry
- a publishable artifact is preferred over legacy chapter files
- failed gate results do not update Canon
- successful publication writes a run snapshot and Canon snapshot

- [ ] **Step 5: Commit the completed phase**

```bash
git add core/story_bible_store.py core/canon_store.py core/release_policy_store.py \
  core/episode_artifact_store.py core/run_snapshot_store.py core/origin_quality.py \
  core/generator.py core/chapter_source.py core/publishing_executor.py \
  core/publishing_runtime.py tests/test_story_bible_store.py tests/test_canon_store.py \
  tests/test_release_policy_store.py tests/test_episode_artifact_store.py \
  tests/test_run_snapshot_store.py tests/test_origin_quality.py \
  tests/test_generator_storage.py tests/test_chapter_source.py \
  tests/test_publishing_executor.py tests/test_publishing_runtime.py
git commit -m "feat: add origin pipeline foundation"
```

## Deferred Follow-Up Plans

Do not expand this plan in place. Later plans should cover:

- planner-driven episode generation
- critic-model quality gates
- marketing packager
- locale pipeline execution
- foreign platform adapters

This keeps the foundation phase independently buildable and testable.
