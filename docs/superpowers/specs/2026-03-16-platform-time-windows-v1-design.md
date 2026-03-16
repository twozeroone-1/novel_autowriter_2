# Platform Time Windows V1 Design

## Goal

Make `ReleasePolicyEngine` actually respect platform-level `default_times` so publication decisions are constrained by per-platform time windows instead of daily limits alone.

## Context

`ReleasePolicyStore` already persists:

- `platforms.<platform>.default_times`

But `release_policy_engine` currently ignores those values. As a result, the system can publish to any enabled platform at any time of day as long as daily limits are not exhausted.

That leaves a clear phase-4 gap against the top-level design, which explicitly calls for platform-specific publication times.

## Scope

This slice adds:

- per-platform time-window checks in `release_policy_engine`
- blocked reason `outside_release_window`
- tests for single-platform and no-platform time matches

This slice does not add:

- weekday-specific platform calendars
- fuzzy windows or grace periods
- separate timezone configuration per platform

## Recommendation

Use exact `HH:MM` matching against the current runtime time.

Why:

- it aligns with the current stored data shape
- it is deterministic and cheap
- it closes the missing policy boundary without introducing scheduler complexity

## Architecture

### `core/release_policy_engine.py`

Extend `_platform_is_allowed_now(...)` to receive `now` and reject a platform when:

- `default_times` is present and non-empty
- current local time does not match any configured `HH:MM`

If `default_times` is empty, keep current behavior and treat the platform as unrestricted by time.

## Decision Rules

- enabled platform + matching time + under daily cap => allowed
- enabled platform + non-matching time => blocked with `outside_release_window`
- all platforms outside their windows => `skip/no_allowed_platforms`

## Testing

### `tests/test_release_policy_engine.py`

Add tests for:

- one platform matching current time while another is blocked by its window
- no platform matching current time leading to `skip`

## Result

This slice makes phase 4 more faithful to the top-level design by turning stored platform times into real policy decisions.
