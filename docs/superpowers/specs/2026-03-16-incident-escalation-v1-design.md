# Incident Escalation V1 Design

## Goal

Fill the remaining phase-4 gap around runtime state escalation by introducing:

- `stopped` runtime state for repeated `quality_incident`
- per-platform blocking after repeated `platform_incident`
- UI surfacing for `stopped`

This slice does not attempt full incident storage or human notification workflows.

## Context

`_2` already has:

- `cooldown`, `paused`, `blocked` runtime states
- `platform_incident`, `credential_incident`, `data_integrity_incident`
- publish history with `incident_type`

What is still missing from the top-level design is escalation logic. Right now:

- quality hard fail blocks the runtime immediately but does not accumulate toward `stopped`
- repeated platform failures are not isolated at the adapter/platform level
- UI does not distinguish a terminal `stopped` state

## Scope

This slice adds:

- release-policy thresholds for quality-stop and platform-block escalation
- history-based escalation in `release_policy_engine`
- quality hard-fail history tagging in `publishing_runtime`
- `stopped` status rendering in publishing UI

This slice does not add:

- separate `incidents/` store
- external notifications
- project-wide daily cap
- multi-day platform quarantine ledger

## Recommendation

Use history-based escalation rather than a new counter store.

Why:

- history is already append-only and reliable enough for v1
- it avoids a second mutable runtime ledger
- it matches the top-level design emphasis on replayable run history

## Architecture

### `core/release_policy_store.py`

Add global defaults:

- `stop_after_quality_incidents`
- `block_platform_after_platform_incidents`

### `core/release_policy_engine.py`

Add escalation rules:

- runtime `stopped` always skips
- if recent consecutive `quality_incident` count reaches threshold, return skip with `next_runtime_status="stopped"`
- if a platform reaches repeated recent platform incidents without an intervening success, block that platform only

Platform blocking should not stop the entire runtime if other platforms remain runnable.

### `core/publishing_runtime.py`

Quality hard fail path should append history with `incident_type="quality_incident"`.

If the current quality incident crosses the threshold, set runtime status to `stopped` immediately instead of `blocked`.

### `ui/publishing.py`

Add a `stopped` branch to the runtime status formatter and relax the reset button wording so it is not specific to `paused`.

## Decision Rules

- repeated `quality_incident` >= threshold => runtime `stopped`
- repeated `platform_incident` for one platform >= threshold => that platform is blocked from future policy decisions
- `credential_incident` remains `paused`
- `data_integrity_incident` remains `blocked` in this slice

Consecutive means:

- count backward from newest history
- stop counting when a record of another incident type appears
- for per-platform blocking, a success for that platform resets the streak

## Testing

### `tests/test_release_policy_engine.py`

Add tests for:

- runtime `stopped` skips immediately
- repeated `quality_incident` produces `stopped`
- repeated `platform_incident` blocks only the affected platform when another is still allowed

### `tests/test_publishing_runtime.py`

Add tests for:

- quality hard fail stores `incident_type="quality_incident"`
- threshold crossing moves runtime to `stopped`

### `tests/test_publishing_ui.py`

Add test for:

- stopped runtime formatting

## Result

This slice makes phase 4 more faithful to the top-level design by turning incidents into runtime state transitions instead of one-off labels.
