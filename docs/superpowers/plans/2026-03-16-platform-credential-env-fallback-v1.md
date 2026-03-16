# Platform Credential Env Fallback V1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow publishing and smoke flows to load platform credentials from environment variables when secure storage is unavailable or empty.

**Architecture:** Keep `core/platform_credentials.py` as the single credential boundary. Add env fallback and precedence logic there, then let existing callers like the smoke runner and publishing executor benefit without new wiring. Document supported variable names in `.env.example`.

**Tech Stack:** Python, unittest, os environment variables, existing publishing credential loader

---

## File Structure

### Modify

- `core/platform_credentials.py`
  - add env normalization and fallback logic to the public loader
- `tests/test_platform_credentials.py`
  - add loader precedence and env fallback tests
- `tests/test_publishing_smoke.py`
  - prove smoke can use env-sourced credentials
- `.env.example`
  - document supported platform credential variables

## Chunk 1: Red tests first

### Task 1: Add failing tests for env fallback behavior

**Files:**
- Modify: `tests/test_platform_credentials.py`
- Modify: `tests/test_publishing_smoke.py`

- [ ] **Step 1: Add failing credential loader tests**

Add tests proving:

- env fallback is used when secure storage is unavailable
- project-scoped env variables override platform-global env variables
- partial env credentials are ignored and return empty payload

- [ ] **Step 2: Add a failing smoke test using env-backed credentials**

Add a smoke-runner test proving it succeeds when the injected credential loader resolves env-backed credentials through the shared loader boundary.

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_platform_credentials tests.test_publishing_smoke -v
```

Expected: FAIL on missing env fallback behavior.

## Chunk 2: Minimal implementation

### Task 2: Implement env fallback in the shared loader

**Files:**
- Modify: `core/platform_credentials.py`
- Modify: `.env.example`

- [ ] **Step 1: Add project/platform env key normalization helpers**

Implement the smallest helpers needed to build:

- `NOVEL_AUTOWRITER_<PROJECT_KEY>_<PLATFORM>_USERNAME/PASSWORD`
- `NOVEL_AUTOWRITER_<PLATFORM>_USERNAME/PASSWORD`

- [ ] **Step 2: Add env fallback to `load_platform_credentials(...)`**

Implement the smallest precedence logic:

- secure storage first
- then project-scoped env
- then platform-global env
- otherwise empty payload

- [ ] **Step 3: Document supported variables in `.env.example`**

Add commented placeholders for Munpia/Novelpia env credential names without putting secrets in the repo.

- [ ] **Step 4: Run focused tests and make them pass**

Run:

```bash
python3 -m unittest tests.test_platform_credentials tests.test_publishing_smoke -v
```

Expected: PASS

## Chunk 3: Regression and commit

### Task 3: Verify the slice and commit

**Files:**
- Modify: all files above

- [ ] **Step 1: Run publishing-focused regression**

Run:

```bash
python3 -m unittest tests.test_platform_credentials tests.test_publishing_smoke tests.test_platform_client_base tests.test_munpia_client tests.test_novelpia_client tests.test_publishing_executor tests.test_publishing_runtime tests.test_publishing_policy tests.test_publishing_incidents tests.test_publishing_ui -v
```

Expected: PASS

- [ ] **Step 2: Run syntax and diff verification**

Run:

```bash
python3 -m py_compile core/platform_credentials.py tests/test_platform_credentials.py tests/test_publishing_smoke.py
git diff --check -- core/platform_credentials.py tests/test_platform_credentials.py tests/test_publishing_smoke.py .env.example docs/superpowers/specs/2026-03-16-platform-credential-env-fallback-v1-design.md docs/superpowers/plans/2026-03-16-platform-credential-env-fallback-v1.md
```

Expected: clean output

- [ ] **Step 3: Commit the slice**

```bash
git add core/platform_credentials.py tests/test_platform_credentials.py tests/test_publishing_smoke.py .env.example docs/superpowers/specs/2026-03-16-platform-credential-env-fallback-v1-design.md docs/superpowers/plans/2026-03-16-platform-credential-env-fallback-v1.md
git commit -m "feat: add env fallback for platform credentials"
```
