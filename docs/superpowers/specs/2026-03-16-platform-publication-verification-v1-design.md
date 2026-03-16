# Platform Publication Verification V1 Design

## Goal

Add a minimum `verify_publication(expected)` boundary to platform adapters so successful uploads are not treated as complete without one more adapter-side confirmation step.

## Context

The top-level design expects platform adapters to expose:

- `login(credentials)`
- `ensure_work(mapping)`
- `upload_episode(payload)`
- `set_publish_options(payload)`
- `verify_publication(expected)`

`_2` now has working upload adapters and a publish packager, but still treats upload completion as final success. That leaves a gap between “submit succeeded” and “publication is plausibly visible or scheduled.”

## Scope

This slice adds:

- `verify_publication(expected)` to the base adapter contract
- minimal Munpia and Novelpia verification implementations
- executor integration so upload success is followed by verification
- verification results persisted into executor platform results

This slice does not add:

- full public-site re-query
- delayed scheduler polling
- platform-specific publication option APIs

## Recommended Approach

### Option A: Treat upload completion as publish completion

Pros:

- no new code

Cons:

- leaves the platform adapter contract incomplete
- ignores the gap the top-level design explicitly calls out

### Option B: Add a lightweight immediate verification pass

Pros:

- satisfies the missing adapter boundary
- keeps scope small
- uses the existing browser state after submission

Cons:

- weaker than future true re-query verification

### Option C: Build full post-publish polling now

Pros:

- strongest signal

Cons:

- much larger scope
- more flaky and platform-specific

## Recommendation

Choose Option B.

Verification v1 should only check immediate, low-cost signals:

- we are no longer on the editor URL
- the completion/viewer URL shape looks correct
- if an episode ID exists, the current URL includes it

## Architecture

### `core/platform_clients/base.py`

Add abstract method:

```python
def verify_publication(self, expected: dict) -> PlatformActionResult:
    ...
```

The `expected` payload stays dict-based in v1 to avoid premature interface growth.

### `core/platform_clients/munpia.py`

Verification rules:

- compute editor URL from `upload_url_template` and `work_id`
- fail retryably if browser is still on editor URL
- if `episode_id` exists, require it in current URL
- otherwise accept any non-editor completion URL

### `core/platform_clients/novelpia.py`

Verification rules:

- compute editor URL using the same helper as upload
- fail retryably if still on editor URL or `write_proc`
- if `episode_id` exists, require it in current URL

### `core/publishing_executor.py`

Changes:

- after `upload_episode(...)` succeeds, build `expected_publication` using packaged data plus actual work/episode identifiers
- call `client.verify_publication(expected_publication)`
- only mark platform success when verification also succeeds
- persist verification outcome in `platform_results[platform]["verification"]`

## Decision Rules

- upload success + verify success => final success
- upload success + verify failure => final failed, usually `retryable`
- upload failure => existing behavior unchanged
- verification exceptions are mapped through `PlatformError`

## Testing

### Updated tests

- `tests/test_platform_client_base.py`
  - base contract still imports and `PlatformActionResult` remains stable

- `tests/test_munpia_client.py`
  - verification succeeds for completed episode URL
  - verification fails retryably when still on editor URL

- `tests/test_novelpia_client.py`
  - verification succeeds for viewer URL
  - verification fails retryably when still on editor or write-proc URL

- `tests/test_publishing_executor.py`
  - executor calls verification after upload success
  - verification failure downgrades platform result to failed

## Non-goals

- public listing verification
- delayed reserved-release verification
- multi-step option-setting APIs
- runtime polling loops

## Result

This slice closes a major part of the remaining phase-3 gap by making adapter success mean “uploaded and immediately verified,” not just “submitted.”
