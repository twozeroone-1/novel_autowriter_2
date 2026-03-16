# Scheduled Reconciliation V1 Design

## Background

`_2` now supports a real reserved-upload boundary for Novelpia.

- `publish_mode="reserved"` can be packaged and sent to the adapter
- `NovelpiaClient` can return `scheduled`
- executor preserves `scheduled`
- runtime/incident handling no longer treats `scheduled` as an immediate failure

That closes the first half of adapter-side scheduling, but not the second half. Right now a reserved submission can end with a top-level success-like outcome without any later reconciliation pass that confirms the episode actually became published after `reserved_at`.

That leaves the control plane in an awkward state:

- `scheduled` exists as a platform result
- there is no follow-up verification loop
- job state cannot distinguish "scheduled and waiting" from "fully finished"
- Canon finalize has to remain conservative because the system cannot prove the publish is complete yet

The top-level system design expects platform adapters to emit `uploaded`, `scheduled`, `published`, or `failed`, and expects the runtime to operate in an incident-driven state model that includes `scheduled`.

## Goal

Add a bounded `scheduled reconciliation v1` path that:

- keeps reserved-upload jobs in a waiting state after successful scheduling
- re-checks them only after `reserved_at`
- confirms publication with a separate follow-up executor path
- finalizes Canon only after real publication confirmation

This slice should close the remaining phase-3/4 gap around site-internal scheduled publishing without introducing a brand-new scheduler subsystem or cross-platform reconciliation framework.

## Approaches

### Option 1. Treat `scheduled` as final success

Pros:

- no extra code path
- simplest runtime behavior

Cons:

- no real publication confirmation
- Canon remains ambiguous
- contradicts the intent of distinct adapter statuses

### Option 2. Add a lightweight reconciliation pass for due scheduled jobs

Pros:

- smallest design that closes the verification gap
- preserves the current publish control plane boundaries
- keeps reserved scheduling honest without requiring a separate service

Cons:

- adds a second executor path
- introduces one more queue/job state

### Option 3. Add a full persistent reconciliation ledger and dedicated polling worker

Pros:

- strongest long-term model
- easiest to scale to many adapters later

Cons:

- too large for the remaining phase-3/4 work
- duplicates information already available in queue/history

This spec chooses option 2.

## Scope

### In scope

- new job/target waiting state for scheduled uploads
- due-time selection for scheduled reconciliation
- executor reconciliation path that verifies without re-uploading
- Novelpia follow-up verification behavior
- runtime state propagation for `scheduled`
- Canon finalize only after reconciliation confirms publication

### Out of scope

- Munpia reserved support
- generic cross-platform scheduled polling framework
- recurring background poll intervals independent from runtime ticks
- reservation edit/cancel flow
- marketing or locale work

## Design

### 1. Job and target states

After an initial reserved upload succeeds with `scheduled`:

- target status should remain `scheduled`
- job status should become `scheduled`
- runtime status should become `scheduled`

This is different from `done`. The queue must keep enough information to revisit the job later.

### 2. Scheduled reconciliation selection

Scheduled reconciliation should not be treated like a new publish slot.

That means:

- it should not wait for daily platform publish windows
- it should not consume `ReleasePolicyEngine` publish slot logic again
- it should run as soon as a scheduled target is due for verification

The runtime should therefore look for due scheduled jobs before normal publish-policy selection.

Due means:

- job status is `scheduled`
- at least one selected target has status `scheduled`
- that target has `reserved_at <= now`

### 3. Executor split

`PublishingExecutor` should keep `publish_job(...)` for real uploads.

Add a second narrow method:

- `reconcile_scheduled_job(job=..., config=...)`

This method should:

- log in to the selected platform client
- avoid `ensure_work(...)` and `upload_episode(...)`
- call adapter verification using the stored target metadata
- return `platform_results` in the same result shape as a normal publish run

This keeps scheduled follow-up as an executor concern, not a runtime hack.

### 4. Novelpia follow-up verification

`NovelpiaClient.verify_publication(expected)` currently works well for:

- immediate publish after redirect
- immediate reserved confirmation that returns `scheduled`

It needs one more path for reconciliation:

- if this is a reserved follow-up and the browser is not already on a useful page, navigate to a work/listing URL derived from `work_id`
- inspect page content for the expected episode title
- if found, return `done`
- if not found, raise `retryable`

This v1 deliberately uses a simple listing-page confirmation rule instead of a more ambitious multi-step crawl.

### 5. Incident and runtime interpretation

`scheduled` should no longer be collapsed into `done`.

`publishing_incidents.py` should distinguish:

- all selected targets `done` -> job `done`, runtime `idle`
- any selected target `scheduled` and no failures -> job `scheduled`, runtime `scheduled`
- mixed `done/scheduled/failed` -> still a platform incident path

This finally gives the runtime a meaningful `scheduled` state from the top-level design.

### 6. Canon finalize gating

Canon finalize should run only when real publication is confirmed.

So:

- initial reserved upload with overall job status `scheduled` must skip Canon apply
- later reconciliation that resolves to `done` may apply Canon

That removes the need for the current conservative workaround that rewrites Canon status late inside runtime.

## Data Flow

### Initial reserved upload

1. runtime selects normal pending job
2. quality/executor path runs as today
3. Novelpia returns `scheduled`
4. incident summary returns `job_status="scheduled"`, `runtime_status="scheduled"`
5. queue persists the job for later reconciliation
6. Canon finalize is skipped

### Later reconciliation pass

1. runtime sees a due scheduled job before normal publish selection
2. runtime calls `executor.reconcile_scheduled_job(...)`
3. adapter verifies listing/publication state
4. if published, incident summary returns `done`
5. runtime finalizes Canon and clears scheduled state
6. if still missing, runtime records retryable platform failure and moves to `cooldown`

## Testing

- `tests/test_novelpia_client.py`
  - reserved follow-up verification navigates and returns `done` when the expected title appears
  - missing title after due reserved publish raises `retryable`
- `tests/test_publishing_policy.py`
  - due scheduled jobs are selected before normal pending jobs
- `tests/test_publishing_executor.py`
  - `reconcile_scheduled_job(...)` logs in and verifies without re-uploading
- `tests/test_publishing_incidents.py`
  - all-scheduled results produce `job_status="scheduled"` and `runtime_status="scheduled"`
- `tests/test_publishing_runtime.py`
  - initial reserved upload persists scheduled job without Canon apply
  - later due reconciliation resolves scheduled job to `done` and applies Canon

## Non-goals

- Munpia reserved scheduling
- repeated polling before `reserved_at`
- per-platform custom reconciliation ledgers
- generic adapter-side scheduled crawler framework
