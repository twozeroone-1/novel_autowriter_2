# Munpia Manual Session Reuse V1 Plan

1. Add red tests for:
   - session path resolution
   - storage-state capable Playwright session wrapper
   - Munpia client preferring saved session over form login
   - bootstrap script saving session state
2. Implement project-scoped session store
3. Extend Playwright session abstraction for `storage_state_path` and `save_storage_state()`
4. Update Munpia client to consume saved session state and return explicit bootstrap guidance on security checkpoint
5. Add `scripts/bootstrap_munpia_session.py`
6. Verify targeted tests, py_compile, and a fresh smoke run
