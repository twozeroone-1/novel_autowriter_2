# Novelpia Reserved Publish V1 Implementation Plan

## Goal

Add real site-internal reserved publishing support for Novelpia, keep Munpia explicitly unsupported, and let executor/runtime treat a successful reserved submission as `scheduled` instead of a failure.

## Files

- `core/platform_clients/novelpia.py`
- `core/platform_clients/munpia.py`
- `core/publishing_executor.py`
- `core/publishing_incidents.py`
- `core/publishing_runtime.py`
- `tests/test_novelpia_client.py`
- `tests/test_munpia_client.py`
- `tests/test_publishing_executor.py`
- `tests/test_publishing_runtime.py`

## Steps

- [ ] Add failing tests for Novelpia reserved option acceptance, reserved submission behavior, and scheduled verification
- [ ] Add failing tests for executor/runtime handling of successful `scheduled` platform results
- [ ] Run focused tests and confirm failure
- [ ] Implement reserved option handling and scheduled verification in `NovelpiaClient`
- [ ] Keep Munpia reserved mode explicitly unsupported
- [ ] Update executor/runtime incident handling so `scheduled` is treated as a non-failure outcome
- [ ] Re-run focused tests
- [ ] Run broader regressions, `py_compile`, and `git diff --check`
