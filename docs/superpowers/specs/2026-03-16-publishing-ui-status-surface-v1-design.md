# Publishing UI Status Surface V1 Design

## Background

`_2` now has a real scheduled publishing flow.

- reserved Novelpia uploads can finish as `scheduled`
- runtime can stay in `scheduled`
- scheduled jobs stay in the queue and later reconcile to `done`

The UI layer has not caught up. `ui/publishing.py` still treats the world as:

- queue jobs are mainly `pending` or `partial_failed`
- runtime is mainly `idle`, `running`, `cooldown`, `blocked`, `stopped`, or `paused`
- history is either simple success or failure

That makes the control plane harder to operate because the backend can already distinguish "waiting for reserved publish" from "fully done", but the operator-facing surface cannot.

## Goal

Add a bounded UI/status slice that makes scheduled publishing visible without redesigning the publishing UI.

This slice should:

- display `scheduled` as a first-class runtime state
- count waiting scheduled jobs in the summary surface
- present queue/history rows in a way that makes scheduled work distinguishable from ordinary failure
- keep the implementation limited to helper/formatting boundaries in `ui/publishing.py`

## Approaches

### Option 1. Leave the UI as-is

Pros:

- no work

Cons:

- backend/runtime meaning is hidden
- scheduled jobs look like incomplete or failed work
- operators cannot tell whether the system is waiting or broken

### Option 2. Add scheduled-aware formatting and summaries to existing helpers

Pros:

- smallest slice
- preserves the current UI structure
- closes the most important observability gap

Cons:

- does not yet redesign the larger publishing UI

### Option 3. Redesign the publishing UI around grouped states

Pros:

- strongest operator experience long-term

Cons:

- too large for the current phase-1~4 closeout
- mixes observability work with broader UI refactoring

This spec chooses option 2.

## Scope

### In scope

- scheduled-aware runtime status label
- queue counting that includes scheduled jobs
- queue/history row formatting that distinguishes scheduled from failure
- runtime detail surface for scheduled mode
- focused publishing UI tests

### Out of scope

- publishing tab layout redesign
- new queue editing interactions
- scheduled reconciliation logic itself
- marketing or locale work

## Design

### 1. Runtime status formatting

`format_publishing_runtime_status(runtime)` should recognize `scheduled`.

Expected behavior:

- `scheduled` with an error or note should render as `예약 대기: ...`
- plain `scheduled` should render as `예약 대기`

This keeps it parallel with `cooldown`, `blocked`, `stopped`, and `paused`.

### 2. Pending-work summary

The top summary metric should treat `scheduled` as active queued work, not as completed work.

So `count_pending_publishing_jobs(queue)` should count:

- `pending`
- `partial_failed`
- `scheduled`

This better matches operational reality because a scheduled job still needs later reconciliation.

### 3. Queue row status surface

The queue table can keep showing raw job status text, but the helper layer should support scheduled jobs cleanly.

That means:

- no filtering or implicit collapse of `scheduled`
- selected platform summary should continue to work for scheduled jobs
- tests should prove the queue table can show a scheduled row without special casing elsewhere

### 4. History row result semantics

History currently maps top-level `success` to `성공` and everything else to `실패`.

That is too coarse once scheduled uploads exist. For UI purposes:

- `success == True` still means `성공`
- `success == False` plus any platform result `status == "scheduled"` should render as `예약`
- otherwise render `실패`

This keeps the underlying history schema unchanged while surfacing the operator-meaningful distinction.

### 5. Runtime detail section

The runtime detail panel should make scheduled mode understandable without a UI redesign.

Minimal additions:

- when runtime status is `scheduled`, current status text already reflects that
- `현재 작업` and `마지막 실행` stay as-is
- `마지막 오류` should continue to show `-` if empty instead of implying failure

No new widgets are needed for this slice.

## Testing

- `tests/test_publishing_ui.py`
  - `format_publishing_runtime_status(...)` returns `예약 대기` for scheduled runtime
  - scheduled queue jobs are included in the pending count
  - queue rows preserve scheduled status
  - history rows render `예약` when platform results contain `scheduled`

## Non-goals

- changing publishing history storage schema
- grouping queue/history by platform
- adding scheduled-specific controls such as cancel or requeue
