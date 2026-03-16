# Publish Packager V1 Design

## Goal

Introduce a dedicated `Publish Packager` boundary so platform upload payload construction is no longer embedded inside `PublishingExecutor`.

## Context

`_2` already has:

- structured source loading via `chapter_source`
- final quality gating before publish
- executor-backed platform upload for Munpia and Novelpia
- publish control plane v1 with runtime snapshots

What is still missing from the top-level design is a real `Publish Packager` layer between quality-approved source material and platform adapters.

Today, `PublishingExecutor` still performs all of these jobs at once:

- source loading
- source override application
- target normalization
- work metadata construction
- `EpisodeUploadRequest` construction
- platform client execution

That is the wrong boundary. It makes adapter work harder to reason about, and it hides the exact package that will be uploaded.

## Scope

This slice adds:

- a dedicated `publish_packager` module
- executor integration so upload payloads are built by the packager
- runtime snapshot persistence for `packager_report.json`

This slice does not add:

- platform-side publication verification
- marketing text packaging
- locale packaging
- adapter interface redesign

## Recommended Approach

### Option A: Keep payload construction inside `PublishingExecutor`

Pros:

- smallest code change

Cons:

- keeps the current responsibility pile
- does not satisfy the top-level design boundary
- makes later verification and marketing packaging harder

### Option B: Add `publish_packager.py` and make executor consume its output

Pros:

- creates a real packaging seam
- keeps executor focused on login / ensure work / upload
- produces a serializable package report that can be snapshotted
- keeps v1 small

Cons:

- adds one new module and tests

### Option C: Redesign platform client interfaces around packager output now

Pros:

- cleaner long-term interface

Cons:

- bigger refactor than needed for v1
- higher regression risk

## Recommendation

Choose Option B.

The packager should normalize upload payloads and expected publication metadata, but should not own browser automation, credentials, or verification.

## Architecture

### `core/publish_packager.py`

Responsibility:

- turn `source_payload + job + platform config` into serializable platform package payloads

Input:

- `project_name`
- `source_payload`
- `job`
- `config`

Output:

```json
{
  "source": {
    "title": "...",
    "episode_id": "ep_012",
    "artifact_status": "publishable"
  },
  "packages": {
    "munpia": {
      "work_id": "work-1",
      "work_metadata": {
        "title": "Project title",
        "description": "desc",
        "genre": "fantasy",
        "age_grade": "general",
        "cover_path": ""
      },
      "upload_request": {
        "episode_title": "Episode 12",
        "content": "# 12화. 계약의 대가\\n\\n본문",
        "publish_mode": "immediate",
        "visibility": "public",
        "reserved_at": null
      },
      "expected_publication": {
        "episode_title": "Episode 12",
        "publish_mode": "immediate",
        "visibility": "public",
        "reserved_at": null
      }
    }
  }
}
```

Notes:

- packages are only created for selected targets
- disabled platform handling remains in executor for v1 to preserve existing behavior
- packager output stays JSON-serializable for snapshots

### `core/publishing_executor.py`

Responsibility after change:

- load source
- apply source override
- ask packager to build packages
- login, ensure work, upload using package payloads

Executor should no longer construct `EpisodeUploadRequest` fields inline from raw job/source values.

### `core/publishing_runtime.py`

Responsibility after change:

- persist `packager_report.json` when executor returns one
- remain unaware of packager internals

## Decision Rules

- `episode_title`
  - prefer target override
  - then job chapter title
  - then source title

- `content`
  - always use the already normalized source payload passed into the packager

- `work_id`
  - prefer target work ID
  - then platform config work ID
  - otherwise remain empty so executor triggers `ensure_work(...)`

- `work_metadata`
  - always normalize from platform config with project-name fallback for title

- `expected_publication`
  - mirror the planned upload request fields needed for future verification

## Testing

### New tests

- `tests/test_publish_packager.py`
  - builds package from selected target and source
  - falls back from target title to job title to source title
  - carries publish mode / visibility / reserved time / work metadata

### Updated tests

- `tests/test_publishing_executor.py`
  - executor consumes packager output instead of building request inline
  - result includes `packager_report`

- `tests/test_publishing_runtime.py`
  - runtime writes `packager_report.json` when executor returns it

## Non-goals

- publication verification via adapter `verify_publication`
- marketing packager
- translation packager
- adapter API redesign

## Result

This slice creates the missing packager seam in the top-level design without over-expanding into verification or marketing work.
