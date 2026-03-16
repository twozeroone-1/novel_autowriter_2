# Novelpia Reserved Publish V1 Design

## Goal

Close the largest remaining phase-3 publication gap by adding real site-internal reserved publishing support for Novelpia while keeping Munpia explicitly unsupported for reserved mode.

This slice aims to make the publish control plane capable of producing a real `scheduled` platform result for at least one production adapter.

## Context

`_2` already has:

- `Publish Packager`
- `set_publish_options(...)`
- post-upload `verify_publication(expected)`
- platform verification after upload

But right now:

- `publish_mode="reserved"` is rejected by both adapters
- executor cannot receive a successful `scheduled` outcome
- top-level design still expects adapters to return `uploaded`, `scheduled`, `published`, or `failed`

The remaining phase-3 gap is not packaging. It is adapter behavior.

## Evidence Review

Reference files from `_1` were checked:

- `core/platform_clients/novelpia.py`
- `core/platform_clients/munpia.py`
- `core/publishing_executor.py`
- `core/publishing_store.py`

They confirmed the older flow and publishing metadata shape, but they did **not** provide additional selector evidence for full reserved scheduling on both platforms.

That means the safest v1 is:

- implement reserved support only for Novelpia
- keep Munpia as explicit `requires_user_action`
- avoid pretending both adapters support the same reserved workflow yet

## Scope

This slice adds:

- real `reserved` handling in `NovelpiaClient.set_publish_options(...)`
- reserved-aware submit behavior in `NovelpiaClient.upload_episode(...)`
- reserved-aware verification that can return `scheduled`
- executor acceptance of successful `scheduled` platform results

This slice intentionally does not add:

- Munpia reserved support
- delayed polling until the reserved publication time
- reserved publish editing/cancel flow
- platform-agnostic scheduled-state reconciliation

## Options

### Option A: Implement reserved support for both adapters now

Pros:

- symmetrical API surface
- phase-3 looks more complete immediately

Cons:

- no selector evidence for Munpia reserved behavior
- high chance of fake or brittle automation
- likely to regress the currently stable immediate publish path

### Option B: Implement reserved support for Novelpia only, keep Munpia explicitly unsupported

Pros:

- honest boundary
- matches current evidence
- closes the `scheduled` status gap with real behavior for one adapter
- smallest safe path toward full phase-3 completion

Cons:

- feature asymmetry between platforms

### Option C: Leave site-internal reserved unsupported and rely only on app-side `scheduled_at`

Pros:

- lowest implementation risk

Cons:

- does not satisfy the top-level design requirement for adapter-side scheduling
- leaves `scheduled` mostly theoretical

## Recommendation

Use **Option B**.

Novelpia already has the stronger writer/editor automation path in `_2`, so it is the correct place to land reserved support first. Munpia should continue to fail loudly instead of pretending to support something it does not.

## Architecture

### `core/platform_clients/novelpia.py`

Extend the adapter in three places.

#### `set_publish_options(payload)`

Current behavior:

- normalize payload
- reject `reserved`

New behavior:

- normalize payload
- allow:
  - `immediate/public`
  - `immediate/private`
  - `reserved/public`
  - `reserved/private`
- require a non-empty `reserved_at` when `publish_mode == "reserved"`
- store the normalized payload in `_pending_publish_options`

For malformed reserved requests, return:

- `PlatformError(..., error_type="requires_user_action")`

#### `upload_episode(request)`

Current behavior:

- fill title/body
- set category from visibility
- submit
- wait for viewer redirect

New behavior:

- read effective options from `_pending_publish_options`
- keep current immediate flow untouched
- for reserved flow:
  - fill the reserved publish controls
  - preserve visibility/category behavior
  - submit using the reserved mode path

The exact selector names should remain config-overridable through `platform_config["selectors"]`.

Reserved support should be added with dedicated selectors such as:

- `episode_publish_mode_reserved`
- `episode_reserved_date`
- `episode_reserved_time`

If required selectors are missing at runtime, fail as:

- `PlatformError(..., error_type="requires_user_action")`

#### `verify_publication(expected)`

Current behavior:

- require that the browser ends on the viewer page
- otherwise raise `retryable`

New behavior:

- when `expected["publish_mode"] != "reserved"`, keep current behavior
- when `expected["publish_mode"] == "reserved"`:
  - allow a reserved/scheduled confirmation state
  - return `PlatformActionResult(status="scheduled", success=True, ...)`
  - do not require the final public viewer page yet

This is the key boundary that makes reserved publish real at the control-plane layer.

### `core/platform_clients/munpia.py`

Keep the current explicit behavior:

- `reserved` remains unsupported
- `set_publish_options(...)` continues to raise `requires_user_action`

No attempt should be made to fake support in v1.

### `core/publishing_executor.py`

Executor should stay structurally the same.

It should simply allow a successful adapter verification result where:

- `verification_result.status == "scheduled"`
- `verification_result.success is True`

That result should flow into `platform_results[platform]["status"]` unchanged.

### `core/publishing_runtime.py`

Runtime should remain mostly coordinator-only.

V1 assumption:

- `scheduled` is a successful platform result for queue/runtime purposes
- Canon finalize policy remains conservative and should not be broadened silently in this slice unless existing success logic already needs adjustment

If the current runtime or incident summarizer treats only `"done"` as success, that behavior must be updated deliberately and tested.

## Data Flow

1. Packager emits `publish_mode` and `reserved_at`.
2. Executor calls `client.set_publish_options(...)`.
3. Novelpia adapter stores normalized reserved options.
4. `upload_episode(...)` applies reserved publish controls and submits.
5. `verify_publication(expected)` inspects the post-submit state:
   - immediate flow -> `done`
   - reserved flow -> `scheduled`
6. Executor records the platform result with the reserved option payload.
7. Runtime and incident summarization treat `scheduled` as a non-failure outcome.

The important separation remains:

- `job.scheduled_at`: when the app starts the upload attempt
- `target.reserved_at`: when the platform should publish internally

These must never be conflated.

## Result Contract

Reserved Novelpia publish should produce a platform result like:

```json
{
  "status": "scheduled",
  "success": true,
  "work_id": "416704",
  "episode_id": "5471585",
  "publish_options": {
    "publish_mode": "reserved",
    "visibility": "public",
    "reserved_at": "2026-03-16T21:00:00+09:00"
  },
  "verification": {
    "status": "scheduled",
    "success": true
  }
}
```

Exact IDs may differ, but the control plane must be able to distinguish:

- immediate successful publish
- reserved successful scheduling
- failed upload

## Testing

### `tests/test_novelpia_client.py`

Add tests for:

- `set_publish_options` accepts valid reserved payload with `reserved_at`
- `set_publish_options` rejects reserved payload without `reserved_at`
- `upload_episode` applies reserved selectors/fields when reserved mode is pending
- `verify_publication` returns `scheduled` when reserved expected payload matches a valid scheduled confirmation state

### `tests/test_munpia_client.py`

Keep or strengthen the existing expectation:

- reserved mode is still rejected with `requires_user_action`

### `tests/test_publishing_executor.py`

Add tests for:

- Novelpia reserved result can surface `scheduled`
- executor preserves `publish_options` and `verification.status == "scheduled"`
- Munpia reserved still fails before upload

### `tests/test_publishing_runtime.py`

Add coordinator tests for:

- `scheduled` platform result is treated as a successful non-failure outcome
- runtime/job status does not regress into `failed` only because adapter returned `scheduled`

## Non-goals

- delayed scheduled-publication polling
- automatic re-verification at the real publish time
- Munpia reserved support
- reserved publish UI redesign
- cross-platform scheduled reconciliation

## Result

This slice gives the system one real adapter that can schedule publication internally and return a truthful `scheduled` outcome.

That closes a major remaining phase-3 gap without overclaiming support on Munpia, where the current evidence is still too weak.
