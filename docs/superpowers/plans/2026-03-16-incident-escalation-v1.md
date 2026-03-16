# Incident Escalation V1 Implementation Plan

> For agentic workers: use executing-plans and test-driven-development. Keep scope to quality-stop escalation, per-platform block escalation, and stopped UI status only.

## Goal

Implement minimal incident escalation so repeated quality failures can stop the runtime and repeated platform failures can block only that platform.

## Files

### Modify

- `core/release_policy_store.py`
- `core/release_policy_engine.py`
- `core/publishing_runtime.py`
- `ui/publishing.py`
- `tests/test_release_policy_engine.py`
- `tests/test_publishing_runtime.py`
- `tests/test_publishing_ui.py`

## Chunk 1: Lock release-policy escalation behavior

- [ ] Add failing tests in `tests/test_release_policy_engine.py`
  - stopped runtime skips
  - repeated quality incidents escalate to stopped
  - repeated platform incidents block one platform but keep another runnable
- [ ] Run focused tests and confirm failure
- [ ] Implement threshold defaults in `core/release_policy_store.py`
- [ ] Implement escalation logic in `core/release_policy_engine.py`
- [ ] Re-run focused release-policy tests

## Chunk 2: Wire quality incidents into runtime and UI

- [ ] Add failing tests in `tests/test_publishing_runtime.py` and `tests/test_publishing_ui.py`
  - quality hard fail writes `incident_type="quality_incident"`
  - threshold crossing sets runtime to `stopped`
  - UI renders stopped status
- [ ] Run focused runtime/UI tests and confirm failure
- [ ] Implement runtime history tagging and immediate stop escalation
- [ ] Implement stopped status formatting in `ui/publishing.py`
- [ ] Re-run focused runtime/UI tests

## Chunk 3: Regression verification

- [ ] Run publishing/release-policy regression suite
- [ ] Run `py_compile` on touched files
- [ ] Run scoped `git diff --check`
- [ ] Commit only slice files
