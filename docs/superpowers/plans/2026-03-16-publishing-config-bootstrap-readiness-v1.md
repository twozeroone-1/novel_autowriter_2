# Publishing Config Bootstrap And Readiness V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap `publishing/config.json` automatically and unify publishing readiness checks across UI and smoke flows.

**Architecture:** Add a small shared readiness module in `core/` so readiness logic lives in one place, then make `PublishingStore` ensure the config file exists on disk before loading. Update `ui/publishing.py`, `ui/operations_dashboard.py`, and `core/publishing_smoke.py` to consume the shared snapshot instead of duplicating readiness checks.

**Tech Stack:** Python, Streamlit, unittest

---

## Chunk 1: PublishingStore Bootstrap

### Task 1: Ensure publishing config exists on disk

**Files:**
- Modify: `core/publishing_store.py`
- Test: `tests/test_publishing_store.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove:
- `load_config()` creates `publishing/config.json` when missing
- the created file contains the default publishing structure

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_publishing_store -v
```

Expected: FAIL because no bootstrap helper exists yet.

- [ ] **Step 3: Write minimal implementation**

Add:
- `PublishingStore.ensure_config_exists()`
- `load_config()` should call it before reading

- [ ] **Step 4: Re-run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_publishing_store -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/publishing_store.py tests/test_publishing_store.py
git commit -m "feat: bootstrap publishing config files"
```

## Chunk 2: Shared Readiness Snapshot

### Task 2: Add shared readiness validator

**Files:**
- Create: `core/publishing_readiness.py`
- Create: `tests/test_publishing_readiness.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- enabled + credentials + work_id + upload_url_template => ready
- missing credentials / work_id / upload_url_template => blockers and recommended actions
- disabled platform remains non-ready without forcing setup blocker text

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_publishing_readiness -v
```

Expected: FAIL because the module does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement:
- `build_publishing_readiness_snapshot(...)`
- platform row builder
- blocker/action helpers

- [ ] **Step 4: Re-run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_publishing_readiness -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/publishing_readiness.py tests/test_publishing_readiness.py
git commit -m "feat: add shared publishing readiness snapshot"
```

## Chunk 3: UI Integration

### Task 3: Make publishing UI and operations dashboard consume shared readiness

**Files:**
- Modify: `ui/publishing.py`
- Modify: `ui/operations_dashboard.py`
- Modify: `tests/test_publishing_ui.py`
- Modify: `tests/test_operations_dashboard.py`

- [ ] **Step 1: Write or update failing tests**

Lock:
- publishing UI snapshot still surfaces blockers and next actions using shared readiness
- operations overview still reports missing credentials/work mapping using the shared wording

- [ ] **Step 2: Run focused tests to verify failure**

Run:

```bash
python3 -m unittest tests.test_publishing_ui tests.test_operations_dashboard -v
```

Expected: FAIL because the code still computes readiness inline.

- [ ] **Step 3: Write minimal implementation**

Refactor:
- `ui/publishing.py` to call the shared readiness module
- `ui/operations_dashboard.py` to reuse the same readiness snapshot and append runtime-specific blockers only

- [ ] **Step 4: Re-run focused tests to verify it passes**

Run:

```bash
python3 -m unittest tests.test_publishing_ui tests.test_operations_dashboard -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/publishing.py ui/operations_dashboard.py tests/test_publishing_ui.py tests/test_operations_dashboard.py
git commit -m "refactor: share publishing readiness across ui surfaces"
```

## Chunk 4: Smoke Integration

### Task 4: Gate smoke runs on shared readiness

**Files:**
- Modify: `core/publishing_smoke.py`
- Modify: `tests/test_publishing_smoke.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- readiness failures short-circuit before client creation
- missing upload_url_template is reported as `requires_user_action`
- ready platforms still proceed to `login -> smoke_check_editor`

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_publishing_smoke -v
```

Expected: FAIL because smoke does not yet use shared readiness.

- [ ] **Step 3: Write minimal implementation**

Update smoke flow to:
- load/bootstrap config
- build readiness snapshot
- immediately fail unready platforms without opening browser clients
- continue only for ready platforms

- [ ] **Step 4: Re-run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_publishing_smoke -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/publishing_smoke.py tests/test_publishing_smoke.py
git commit -m "feat: use readiness snapshot in publishing smoke"
```

## Chunk 5: Regression Verification

### Task 5: Verify the integrated slice

**Files:**
- Modify: `docs/superpowers/plans/2026-03-16-publishing-config-bootstrap-readiness-v1.md`

- [ ] **Step 1: Run curated regression**

Run:

```bash
python3 -m unittest \
  tests.test_publishing_store \
  tests.test_publishing_readiness \
  tests.test_publishing_smoke \
  tests.test_publishing_ui \
  tests.test_operations_dashboard -v
```

Expected: PASS

- [ ] **Step 2: Run py_compile**

Run:

```bash
python3 -m py_compile \
  core/publishing_store.py \
  core/publishing_readiness.py \
  core/publishing_smoke.py \
  ui/publishing.py \
  ui/operations_dashboard.py \
  tests/test_publishing_store.py \
  tests/test_publishing_readiness.py \
  tests/test_publishing_smoke.py \
  tests/test_publishing_ui.py \
  tests/test_operations_dashboard.py
```

Expected: no output

- [ ] **Step 3: Run diff check**

Run:

```bash
git diff --check -- \
  core/publishing_store.py \
  core/publishing_readiness.py \
  core/publishing_smoke.py \
  ui/publishing.py \
  ui/operations_dashboard.py \
  tests/test_publishing_store.py \
  tests/test_publishing_readiness.py \
  tests/test_publishing_smoke.py \
  tests/test_publishing_ui.py \
  tests/test_operations_dashboard.py \
  docs/superpowers/plans/2026-03-16-publishing-config-bootstrap-readiness-v1.md
```

Expected: no output

- [ ] **Step 4: Commit**

```bash
git add core/publishing_store.py core/publishing_readiness.py core/publishing_smoke.py ui/publishing.py ui/operations_dashboard.py tests/test_publishing_store.py tests/test_publishing_readiness.py tests/test_publishing_smoke.py tests/test_publishing_ui.py tests/test_operations_dashboard.py docs/superpowers/plans/2026-03-16-publishing-config-bootstrap-readiness-v1.md
git commit -m "test: verify publishing readiness bootstrap regression"
```
