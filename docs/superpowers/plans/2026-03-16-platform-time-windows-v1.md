# Platform Time Windows V1 Implementation Plan

## Goal

Use `default_times` during release-policy evaluation so each platform can open or close independently by time of day.

## Files

- `core/release_policy_engine.py`
- `tests/test_release_policy_engine.py`

## Steps

- [ ] Add failing tests for matching and non-matching platform windows
- [ ] Run focused release-policy tests and confirm failure
- [ ] Implement exact `HH:MM` window checks
- [ ] Re-run release-policy tests
- [ ] Run broader publishing regressions plus `py_compile` and `git diff --check`
