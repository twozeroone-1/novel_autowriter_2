# Automation Canon Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop unattended automation from auto-writing freeform `state` and `summary_of_previous` by default, while recording non-authoritative Canon candidate data for later structured extraction work.

**Architecture:** Keep `core/automation_runtime.py` as the integration boundary for unattended generation. Flip automation defaults so legacy context writes are explicit opt-in only, and add a small Canon-candidate helper that records structured candidate payloads in automation history without mutating `CanonStore`. Preserve backward compatibility for existing projects that already saved `context_updates.state=true` and `context_updates.summary=true`.

**Tech Stack:** Python, unittest, existing `AutomationStore`, `AutomationRuntime`, `Automator`

---

## Chunk 1: Automation defaults and runtime behavior

### Task 1: Flip unattended context-update defaults

**Files:**
- Modify: `core/automation_store.py`
- Test: `tests/test_automation_store.py`

- [ ] **Step 1: Write the failing test**

```python
def test_load_automation_config_defaults_disable_legacy_context_updates(self):
    config = store.load_config()
    assert config["context_updates"]["state"] is False
    assert config["context_updates"]["summary"] is False
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `python3 -m unittest tests.test_automation_store.TestAutomationStore.test_load_automation_config_defaults_disable_legacy_context_updates -v`
Expected: FAIL because the default config still enables both legacy fields.

- [ ] **Step 3: Write the minimal implementation**

In `core/automation_store.py`, change `DEFAULT_AUTOMATION_CONFIG["context_updates"]` so:

```python
"context_updates": {
    "state": False,
    "summary": False,
},
```

Keep merge behavior unchanged so previously saved explicit `true` values still override the defaults.

- [ ] **Step 4: Run the targeted test to verify it passes**

Run: `python3 -m unittest tests.test_automation_store.TestAutomationStore.test_load_automation_config_defaults_disable_legacy_context_updates -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_automation_store.py core/automation_store.py
git commit -m "test: disable legacy automation context defaults"
```

### Task 2: Make runtime skip legacy context writes unless explicitly enabled

**Files:**
- Modify: `core/automation_runtime.py`
- Test: `tests/test_automation_runtime.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_runtime_skips_legacy_context_apply_by_default():
    ...
    assert fake_automator.apply_calls == []
    assert history[0]["context_update"]["legacy"]["status"] == "skipped"

def test_runtime_applies_legacy_context_updates_when_explicitly_enabled():
    ...
    assert fake_automator.apply_calls == [("state", "summary")]
    assert history[0]["context_update"]["legacy"]["status"] == "applied"
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_automation_runtime.TestAutomationRuntime.test_runtime_skips_legacy_context_apply_by_default tests.test_automation_runtime.TestAutomationRuntime.test_runtime_applies_legacy_context_updates_when_explicitly_enabled -v`
Expected: FAIL because the runtime still auto-applies suggestions on the default path and the history schema does not have the `legacy` block yet.

- [ ] **Step 3: Write the minimal implementation**

In `core/automation_runtime.py`:

- rename the helper intent from “apply” to “process” if helpful, but keep scope small
- compute the legacy apply decision from `context_updates.state` and `context_updates.summary`
- return a nested status payload like:

```python
{
    "legacy": {
        "status": "skipped" | "applied" | "partial_failure",
        "applied": {
            "state": bool,
            "summary_of_previous": bool,
        },
        "backup": {...},  # only when applied
        "error": "...",   # only on failure
    },
    "canon_candidate": {...},
}
```

When both legacy toggles are false, do not call `automator.apply_context_updates()`.

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_automation_runtime.TestAutomationRuntime.test_runtime_skips_legacy_context_apply_by_default tests.test_automation_runtime.TestAutomationRuntime.test_runtime_applies_legacy_context_updates_when_explicitly_enabled -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_automation_runtime.py core/automation_runtime.py
git commit -m "feat: gate legacy automation context updates"
```

## Chunk 2: Canon candidate recording

### Task 3: Record structured Canon candidates in automation history without mutating CanonStore

**Files:**
- Create: `core/canon_candidate.py`
- Modify: `core/automation_runtime.py`
- Test: `tests/test_automation_runtime.py`

- [ ] **Step 1: Write the failing test**

```python
def test_runtime_records_canon_candidate_from_cycle_result():
    fake_automator.result_override = {
        "canon_update": {
            "people": {"lead": {"mood": "angry"}},
            "hooks": ["new hook"],
        }
    }
    ...
    assert history[0]["context_update"]["canon_candidate"]["status"] == "recorded"
    assert history[0]["context_update"]["canon_candidate"]["candidate"]["people"]["lead"]["mood"] == "angry"
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `python3 -m unittest tests.test_automation_runtime.TestAutomationRuntime.test_runtime_records_canon_candidate_from_cycle_result -v`
Expected: FAIL because there is no Canon candidate helper or runtime history block yet.

- [ ] **Step 3: Write the minimal implementation**

Create `core/canon_candidate.py` with:

- a normalizer that accepts partial Canon updates using the existing `people/resources/hooks/timeline` shape
- a helper to build a history-safe record

In `core/automation_runtime.py`, call that helper after `run_single_cycle()` completes and include the result under `context_update["canon_candidate"]`.

Rules:
- do not write to `CanonStore`
- if `result.get("canon_update")` is missing or invalid, record `status: "missing"`
- if valid but empty, record `status: "empty"`
- only persist the normalized candidate payload in history

- [ ] **Step 4: Run the targeted test to verify it passes**

Run: `python3 -m unittest tests.test_automation_runtime.TestAutomationRuntime.test_runtime_records_canon_candidate_from_cycle_result -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_automation_runtime.py core/automation_runtime.py core/canon_candidate.py
git commit -m "feat: record automation canon candidates"
```

## Chunk 3: Verification

### Task 4: Run focused and broader regression verification

**Files:**
- Test: `tests/test_automation_store.py`
- Test: `tests/test_automation_runtime.py`
- Test: `tests/test_context_manager.py`
- Test: `tests/test_publishing_runtime.py`

- [ ] **Step 1: Run focused automation tests**

Run: `python3 -m unittest tests.test_automation_store tests.test_automation_runtime -v`
Expected: PASS

- [ ] **Step 2: Run broader origin-pipeline regression tests**

Run: `python3 -m unittest tests.test_context_manager tests.test_generator_storage tests.test_chapter_source tests.test_publishing_executor tests.test_publishing_runtime tests.test_story_bible_store tests.test_canon_store tests.test_release_policy_store tests.test_episode_artifact_store tests.test_run_snapshot_store tests.test_origin_quality tests.test_automation_store tests.test_automation_runtime -v`
Expected: PASS

- [ ] **Step 3: Run syntax verification on touched production files**

Run: `python3 -m py_compile core/automation_store.py core/automation_runtime.py core/canon_candidate.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-03-14-automation-canon-integration.md
git commit -m "docs: add automation canon integration plan"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-14-automation-canon-integration.md`. Ready to execute?
