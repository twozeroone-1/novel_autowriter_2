# Platform Publish Options V1 Implementation Plan

## Goal

Add `set_publish_options(...)` as an explicit adapter boundary and route executor through it.

## Files

- `core/platform_clients/base.py`
- `core/platform_clients/munpia.py`
- `core/platform_clients/novelpia.py`
- `core/publishing_executor.py`
- `tests/test_platform_client_base.py`
- `tests/test_munpia_client.py`
- `tests/test_novelpia_client.py`
- `tests/test_publishing_executor.py`

## Steps

- [ ] Add failing tests for adapter contract and executor sequencing
- [ ] Run focused adapter/executor tests and confirm failure
- [ ] Implement pending publish-option handling in adapters
- [ ] Implement executor call order and option persistence
- [ ] Re-run focused tests
- [ ] Run broader publishing regressions, `py_compile`, and `git diff --check`
