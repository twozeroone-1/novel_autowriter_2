# Munpia Session UI Guidance V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Munpia session status and bootstrap guidance to the publishing UI, with a best-effort launcher for the manual session bootstrap command.

**Architecture:** Keep the interactive login itself outside Streamlit. Add a small launcher/helper layer for command construction and terminal launch, then surface state and actions in `ui/publishing.py`.

**Tech Stack:** Python, Streamlit, subprocess, existing publishing/session stores.

---

### Task 1: Session Guidance Helpers

**Files:**
- Create: `core/munpia_session_launcher.py`
- Modify: `tests/test_publishing_ui.py`

- [ ] Write failing tests for bootstrap command/session guidance helpers
- [ ] Run targeted tests and confirm failure
- [ ] Implement minimal command/launcher helpers
- [ ] Re-run targeted tests and confirm pass

### Task 2: Publishing UI Integration

**Files:**
- Modify: `ui/publishing.py`
- Modify: `tests/test_publishing_ui.py`

- [ ] Write failing tests for Munpia session status/next-action integration
- [ ] Run targeted tests and confirm failure
- [ ] Implement minimal UI snapshot/helper integration
- [ ] Re-run targeted tests and confirm pass

### Task 3: Verification

**Files:**
- Modify: none
- Test: `tests/test_publishing_ui.py`

- [ ] Run curated UI/publishing regression
- [ ] Run `py_compile`
- [ ] Run `git diff --check`
