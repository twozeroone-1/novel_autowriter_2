# Publishing Smoke Test Command V1 Design

## Background

Phases 1-4 are now functionally closed for v1 Korean-origin automation, but the upstream design still calls for real-platform smoke validation before the system should be treated as operationally trustworthy.

Today `_2` has:

- platform credentials in secure storage
- adapter boundaries for Munpia and Novelpia
- publish runtime, packager, policy, and incident handling
- UI buttons that can trigger real publishing work

What it does **not** have is a standard, non-destructive smoke command that checks whether a project is actually ready to publish on real platform accounts.

That leaves the last operational validation step too informal:

- operators must use the Streamlit UI manually
- there is no standard command for "is this project platform-ready right now?"
- there is no easy preflight check before enabling unattended publishing

## Goal

Add a bounded, non-destructive smoke test command for publishing readiness.

This command should:

- load a project's publishing configuration and credentials
- check selected platforms without uploading or creating content
- verify login succeeds
- verify the mapped work's upload editor can be reached and expected fields exist
- return a structured result and exit non-zero when any selected platform is not ready

## Approaches

### Option 1. Manual UI-only smoke checks

Pros:

- no code

Cons:

- inconsistent
- harder to automate in release checklists
- no standard structured report

### Option 2. Non-destructive smoke command with login + editor access checks

Pros:

- safest useful signal
- reuses the existing adapter boundary
- supports real-platform preflight without risking accidental uploads

Cons:

- adds a small adapter-side smoke-check method

### Option 3. Private/draft upload dry-run

Pros:

- strongest end-to-end proof

Cons:

- too risky for a default smoke path
- still creates or mutates platform data

This spec chooses option 2.

## Scope

### In scope

- a smoke runner module
- a thin CLI script or entrypoint
- adapter-level non-destructive editor access checks
- structured stdout JSON report
- non-zero exit code on failure

### Out of scope

- actual episode upload
- work creation
- queue execution
- report persistence
- automatic credential prompting

## Design

### 1. Smoke runner boundary

Add `core/publishing_smoke.py`.

Responsibilities:

- load publishing config
- determine which platforms to check
- load credentials
- instantiate clients
- run a narrow smoke flow per platform
- aggregate a JSON-serializable report

It should not:

- mutate queue/runtime/history
- create works
- upload episodes

### 2. Adapter smoke contract

Add a narrow adapter capability:

- `smoke_check_editor(work_id: str) -> PlatformActionResult`

Behavior:

- requires login to have happened first
- navigates to the platform's upload/editor URL for the configured `work_id`
- verifies the required editor fields are present
- returns `done/success=True` on readiness
- raises `PlatformError` on failure

This stays intentionally smaller than `upload_episode(...)`.

### 3. Smoke command inputs

V1 command inputs:

- `project_name`
- optional platform filter list
- optional `headless` override

Platform selection rules:

- if explicit platforms are passed, only check those
- otherwise check all enabled platforms in publishing config

### 4. Smoke pass failure rules

A selected platform fails smoke if any of these are true:

- credentials missing
- platform disabled when explicitly selected
- `work_id` missing
- login fails
- editor page cannot be reached
- required editor selectors are missing

Failure classification should preserve existing adapter error types where possible:

- `requires_user_action`
- `retryable`
- `permanent`

### 5. Output model

The runner returns a report shaped like:

- `project_name`
- `checked_platforms`
- `success`
- `platform_results`

Each platform result should include:

- `status`
- `success`
- `error_type`
- `error_text`
- `work_id`

The CLI prints the report as JSON and exits:

- `0` if all selected platforms pass
- `1` otherwise

## Data Flow

1. operator runs smoke command with project name
2. runner loads publishing config
3. runner resolves selected platforms
4. for each platform:
   - load credentials
   - instantiate client
   - login
   - smoke-check editor access for `work_id`
5. runner aggregates results
6. CLI prints JSON and exits with pass/fail status

## Testing

- `tests/test_publishing_smoke.py`
  - success when a fake client logs in and editor check passes
  - failure when credentials are missing
  - failure when `work_id` is missing
  - failure when explicit platform is disabled
  - platform filtering works
- `tests/test_munpia_client.py`
  - smoke editor check validates Munpia editor selectors
- `tests/test_novelpia_client.py`
  - smoke editor check validates Novelpia editor selectors

## Non-goals

- saving smoke reports to disk
- running through `PublishingRuntime`
- creating or mutating platform works
- validating reserved publish flows separately from editor readiness
