# Publish Packager V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated publish packager so platform upload payloads are built outside `PublishingExecutor` and can be snapshotted by the runtime.

**Architecture:** Keep `publish_packager` as a pure packaging boundary that converts normalized source plus job/config data into JSON-serializable platform packages. `PublishingExecutor` consumes those packages to build adapter requests, and `PublishingRuntime` persists the returned `packager_report.json`.

**Tech Stack:** Python, unittest, existing chapter source / publishing executor / publishing runtime modules, platform client dataclasses

---

## File Structure

### New files

- `core/publish_packager.py`
  - packaging boundary for platform upload payloads
- `tests/test_publish_packager.py`
  - focused unit tests for package normalization

### Modified files

- `core/publishing_executor.py`
  - consume packager output instead of building upload requests inline
- `core/publishing_runtime.py`
  - persist `packager_report.json` when present
- `tests/test_publishing_executor.py`
  - assert executor uses the packager
- `tests/test_publishing_runtime.py`
  - assert runtime snapshots the packager report

## Chunk 1: Add the packager core

### Task 1: Create focused packager tests first

**Files:**
- Create: `core/publish_packager.py`
- Create: `tests/test_publish_packager.py`

- [ ] **Step 1: Write the failing packager tests**

Create `tests/test_publish_packager.py` with cases that lock:

- selected target packages include work metadata, upload request, and expected publication
- episode title fallback order is target title -> job chapter title -> source title
- publish mode / visibility / reserved time are preserved

- [ ] **Step 2: Run the focused packager tests to verify they fail**

Run: `python3 -m unittest tests.test_publish_packager -v`

Expected: FAIL because `core/publish_packager.py` does not exist yet.

- [ ] **Step 3: Implement the minimal packager**

Create `core/publish_packager.py` with:

- `_normalize_work_metadata(...)`
- `_resolve_episode_title(...)`
- `_build_platform_package(...)`
- `build_publish_packages(...)`

Rules:

- only selected targets produce packages
- packages stay JSON-serializable
- `content` always comes from normalized source payload
- work title falls back to `project_name`

- [ ] **Step 4: Re-run the focused packager tests**

Run: `python3 -m unittest tests.test_publish_packager -v`

Expected: PASS

- [ ] **Step 5: Commit chunk 1**

```bash
git add core/publish_packager.py tests/test_publish_packager.py
git commit -m "feat: add publish packager core"
```

## Chunk 2: Rewire executor to consume packager output

### Task 2: Add executor tests first

**Files:**
- Modify: `core/publishing_executor.py`
- Modify: `tests/test_publishing_executor.py`

- [ ] **Step 1: Write the failing executor integration tests**

Extend `tests/test_publishing_executor.py` with cases that lock:

- executor calls `build_publish_packages(...)`
- upload request fields come from packager output, not inline construction
- result includes `packager_report`

- [ ] **Step 2: Run the focused executor tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_executor -v`

Expected: FAIL because executor is still constructing payloads inline.

- [ ] **Step 3: Implement executor integration**

Update `core/publishing_executor.py`:

- import `build_publish_packages`
- build packages after source loading and source override
- loop through package entries
- convert packaged `work_metadata` into `PlatformWorkMetadata`
- convert packaged `upload_request` into `EpisodeUploadRequest`
- return `packager_report` alongside existing result payload

- [ ] **Step 4: Re-run the focused executor tests**

Run: `python3 -m unittest tests.test_publishing_executor tests.test_publish_packager -v`

Expected: PASS

- [ ] **Step 5: Commit chunk 2**

```bash
git add core/publishing_executor.py tests/test_publishing_executor.py
git commit -m "feat: route executor through publish packager"
```

## Chunk 3: Snapshot packager output in runtime

### Task 3: Add runtime tests first

**Files:**
- Modify: `core/publishing_runtime.py`
- Modify: `tests/test_publishing_runtime.py`

- [ ] **Step 1: Add failing runtime tests**

Extend `tests/test_publishing_runtime.py` with a case that locks:

- `packager_report.json` is written when executor returns `packager_report`

- [ ] **Step 2: Run the focused runtime tests to verify they fail**

Run: `python3 -m unittest tests.test_publishing_runtime -v`

Expected: FAIL because runtime does not yet persist a packager snapshot.

- [ ] **Step 3: Implement runtime snapshot persistence**

Update `core/publishing_runtime.py`:

- after executor result, write `packager_report.json` when `result["packager_report"]` exists

Do not add packager business logic to runtime.

- [ ] **Step 4: Re-run the focused runtime tests**

Run: `python3 -m unittest tests.test_publishing_runtime tests.test_publishing_executor tests.test_publish_packager -v`

Expected: PASS

- [ ] **Step 5: Commit chunk 3**

```bash
git add core/publishing_runtime.py tests/test_publishing_runtime.py
git commit -m "feat: persist publish packager snapshots"
```

## Chunk 4: Regression verification

### Task 4: Run regressions and syntax checks

**Files:**
- No new files; verification only

- [ ] **Step 1: Run focused packager/executor/runtime regressions**

Run:

```bash
python3 -m unittest \
  tests.test_publish_packager \
  tests.test_publishing_executor \
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
  tests.test_publish_packager \
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
  core/publish_packager.py \
  core/publishing_executor.py \
  core/publishing_runtime.py \
  tests/test_publish_packager.py \
  tests/test_publishing_executor.py \
  tests/test_publishing_runtime.py

git diff --check -- \
  core/publish_packager.py \
  core/publishing_executor.py \
  core/publishing_runtime.py \
  tests/test_publish_packager.py \
  tests/test_publishing_executor.py \
  tests/test_publishing_runtime.py
```

Expected: no syntax or whitespace errors
