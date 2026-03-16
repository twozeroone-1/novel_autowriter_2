# Context Manager Decomposition v1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `ContextManager` into a smaller facade by extracting shadow-compatibility, character normalization, and prompt-section responsibilities into focused helper modules while preserving the current public API and compatibility behavior.

**Architecture:** Keep `ContextManager` as the public entry point used by generation, review, and UI code, but move mixed internals into helper modules under `core/`. Rewire the facade incrementally with TDD so structured-store precedence, legacy shadow writes, and prompt text behavior all remain stable while `context.py` becomes coordinator-oriented.

**Tech Stack:** Python, unittest, existing `StoryBibleStore`, `ContextStateStore`, `PlotStore`, `CanonStore`, `ReleasePolicyStore`, `atomic_write_json`, existing context and UI regression tests

---

## File Structure

### New files

- `core/context_story_bible_shadow.py`
  - story-bible shadow defaults, raw `config.json` reads, normalization, and write-through
- `core/context_state_shadow.py`
  - legacy `state` and `summary_of_previous` fallback reads and write-through helpers
- `core/context_characters.py`
  - character normalization and validation helpers
- `core/context_prompt_sections.py`
  - section formatting helpers and final generation prompt assembly
- `tests/test_context_story_bible_shadow.py`
  - focused tests for story-bible shadow normalization and write-through
- `tests/test_context_state_shadow.py`
  - focused tests for state fallback and legacy shadow writes
- `tests/test_context_characters.py`
  - focused tests for character normalization rules
- `tests/test_context_prompt_sections.py`
  - focused tests for section formatting and final prompt assembly

### Modified files

- `core/context.py`
  - shrink into facade plus collaborator wiring
- `tests/test_context_manager.py`
  - keep facade-level guarantees only; remove pure helper-detail assertions
- `tests/test_ui_helpers.py`
  - update only if prompt-assembly or facade call expectations need minor adaptation
- `tests/test_reviewer.py`
  - update only if prompt-section helper extraction affects stubbing boundaries

### Existing files to reference

- `core/story_bible_store.py`
- `core/context_state_store.py`
- `core/plot_store.py`
- `core/canon_store.py`
- `core/release_policy_store.py`
- `core/generator.py`
- `core/reviewer.py`
- `ui/workspace.py`
- `ui/chapters.py`

## Chunk 1: Extract shadow compatibility helpers

### Task 1: Add story-bible shadow helper

**Files:**
- Create: `core/context_story_bible_shadow.py`
- Create: `tests/test_context_story_bible_shadow.py`
- Modify: `core/context.py`

- [ ] **Step 1: Write the failing story-bible shadow tests**

Create `tests/test_context_story_bible_shadow.py` with cases like:

```python
import json
import tempfile
import unittest
from pathlib import Path

from core.context_story_bible_shadow import (
    DEFAULT_STORY_BIBLE_SHADOW,
    load_story_bible_shadow_payload,
    write_story_bible_shadow,
)


class TestContextStoryBibleShadow(unittest.TestCase):
    def test_load_story_bible_shadow_payload_normalizes_missing_and_non_string_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text('{"worldview": 123, "state": null}', encoding="utf-8")

            payload = load_story_bible_shadow_payload(config_path)

            self.assertEqual(payload["worldview"], "123")
            self.assertEqual(payload["tone_and_manner"], DEFAULT_STORY_BIBLE_SHADOW["tone_and_manner"])
            self.assertEqual(payload["continuity"], DEFAULT_STORY_BIBLE_SHADOW["continuity"])

    def test_write_story_bible_shadow_preserves_non_story_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps({"state": "kept", "summary_of_previous": "kept"}, ensure_ascii=False),
                encoding="utf-8",
            )

            write_story_bible_shadow(
                config_path,
                worldview="new world",
                tone_and_manner="new style",
                continuity="new rules",
            )

            payload = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "kept")
            self.assertEqual(payload["summary_of_previous"], "kept")
            self.assertEqual(payload["worldview"], "new world")
```

- [ ] **Step 2: Run the focused story-bible shadow tests to verify they fail**

Run: `python3 -m unittest tests.test_context_story_bible_shadow -v`

Expected: FAIL because `core/context_story_bible_shadow.py` does not exist yet.

- [ ] **Step 3: Write the minimal story-bible shadow helper**

Create `core/context_story_bible_shadow.py` with:

- `DEFAULT_STORY_BIBLE_SHADOW`
- `load_raw_config_payload(config_path: Path) -> dict`
- `normalize_story_bible_shadow_payload(payload: dict | list) -> dict`
- `load_story_bible_shadow_payload(config_path: Path) -> dict`
- `write_story_bible_shadow_payload(config_path: Path, payload: dict) -> None`
- `write_story_bible_shadow(config_path: Path, *, worldview: str, tone_and_manner: str, continuity: str) -> None`

Keep behavior aligned with the current `ContextManager` logic:

- non-dict config payloads fall back to defaults
- story-bible values are coerced to strings
- unrelated config keys remain untouched when story-bible fields are written

- [ ] **Step 4: Re-run the focused story-bible shadow tests**

Run: `python3 -m unittest tests.test_context_story_bible_shadow -v`

Expected: PASS

### Task 2: Add state shadow helper

**Files:**
- Create: `core/context_state_shadow.py`
- Create: `tests/test_context_state_shadow.py`
- Modify: `core/context.py`

- [ ] **Step 1: Write the failing state-shadow tests**

Create `tests/test_context_state_shadow.py` with cases like:

```python
import json
import tempfile
import unittest
from pathlib import Path

from core.context_state_store import DEFAULT_CONTEXT_STATE
from core.context_state_shadow import load_state_shadow_snapshot, write_legacy_state_shadow


class TestContextStateShadow(unittest.TestCase):
    def test_load_state_shadow_snapshot_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            snapshot = load_state_shadow_snapshot(config_path)
            self.assertEqual(snapshot, DEFAULT_CONTEXT_STATE)

    def test_write_legacy_state_shadow_updates_only_target_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps({"worldview": "kept"}, ensure_ascii=False), encoding="utf-8")

            write_legacy_state_shadow(config_path, state="new state", summary_of_previous=None)

            payload = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["worldview"], "kept")
            self.assertEqual(payload["state"], "new state")
            self.assertNotIn("summary_of_previous", payload)
```

- [ ] **Step 2: Run the focused state-shadow tests to verify they fail**

Run: `python3 -m unittest tests.test_context_state_shadow -v`

Expected: FAIL because `core/context_state_shadow.py` does not exist yet.

- [ ] **Step 3: Write the minimal state-shadow helper**

Create `core/context_state_shadow.py` with:

- `load_state_shadow_snapshot(config_path: Path) -> dict`
- `write_legacy_state_shadow(config_path: Path, *, state: str | None = None, summary_of_previous: str | None = None) -> None`

Reuse `DEFAULT_CONTEXT_STATE` and preserve current compatibility rules:

- fallback to defaults when legacy values are missing
- coerce non-string values to strings
- update only the requested keys

- [ ] **Step 4: Re-run the focused state-shadow tests**

Run: `python3 -m unittest tests.test_context_story_bible_shadow tests.test_context_state_shadow -v`

Expected: PASS

- [ ] **Step 5: Rewire `ContextManager` to use the two shadow helpers**

Modify `core/context.py` so that:

- raw config load/normalize/write logic for story-bible shadow is delegated
- state shadow fallback/write logic is delegated
- no public method names change yet

Do not extract characters or prompt assembly in this task.

- [ ] **Step 6: Run facade regressions for affected behavior**

Run:

```bash
python3 -m unittest \
  tests.test_context_story_bible_shadow \
  tests.test_context_state_shadow \
  tests.test_context_manager -v
```

Expected: PASS

- [ ] **Step 7: Commit chunk 1**

```bash
git add core/context_story_bible_shadow.py core/context_state_shadow.py
git add tests/test_context_story_bible_shadow.py tests/test_context_state_shadow.py
git add core/context.py tests/test_context_manager.py
git commit -m "refactor: extract context shadow helpers"
```

## Chunk 2: Extract characters and prompt assembly helpers

### Task 3: Add character helper

**Files:**
- Create: `core/context_characters.py`
- Create: `tests/test_context_characters.py`
- Modify: `core/context.py`

- [ ] **Step 1: Write the failing character-helper tests**

Create `tests/test_context_characters.py` with cases like:

```python
import unittest

from core.context_characters import normalize_characters


class TestContextCharacters(unittest.TestCase):
    def test_normalize_characters_skips_invalid_items(self):
        characters = normalize_characters(
            [
                {"id": "char_001", "name": "Lead", "role": "Lead", "description": "desc", "traits": ["calm"]},
                {"id": "char_002", "name": "Broken"},
            ]
        )
        self.assertEqual(len(characters), 1)
        self.assertEqual(characters[0]["id"], "char_001")

    def test_normalize_characters_discards_blank_traits(self):
        characters = normalize_characters(
            [
                {
                    "id": "char_001",
                    "name": "Lead",
                    "role": "Lead",
                    "description": "desc",
                    "traits": ["calm", "", None],
                }
            ]
        )
        self.assertEqual(characters[0]["traits"], ["calm"])
```

- [ ] **Step 2: Run the focused character-helper tests to verify they fail**

Run: `python3 -m unittest tests.test_context_characters -v`

Expected: FAIL because `core/context_characters.py` does not exist yet.

- [ ] **Step 3: Write the minimal character helper**

Create `core/context_characters.py` with:

- `normalize_character(raw_char: object) -> dict | None`
- `normalize_characters(chars: list | dict) -> list[dict]`

Move current normalization semantics out of `ContextManager` unchanged.

- [ ] **Step 4: Re-run the focused character-helper tests**

Run: `python3 -m unittest tests.test_context_characters -v`

Expected: PASS

### Task 4: Add prompt section helper

**Files:**
- Create: `core/context_prompt_sections.py`
- Create: `tests/test_context_prompt_sections.py`
- Modify: `core/context.py`

- [ ] **Step 1: Write the failing prompt-helper tests**

Create `tests/test_context_prompt_sections.py` with cases like:

```python
import unittest

from core.context_prompt_sections import build_generation_prompt, build_plot_block


class TestContextPromptSections(unittest.TestCase):
    def test_build_plot_block_returns_empty_when_plot_disabled(self):
        block = build_plot_block(plot_outline="stored plot", include_plot=False, plot_strength="balanced")
        self.assertEqual(block, "")

    def test_build_generation_prompt_includes_all_sections(self):
        prompt = build_generation_prompt(
            worldview_context="[STORY BIBLE]\\nworld",
            continuity_context="[CONTINUITY]\\nrules",
            canon_context="[CANON FACTS]\\n{}",
            release_policy_context="[RELEASE POLICY]\\n{}",
            state_context="[STATE]\\nstate",
            character_context="[주요 등장인물 프로필]\\n- lead",
            plot_block="[PLOT OUTLINE]\\nplot",
            user_instruction="next episode",
            length_goal=5000,
        )
        self.assertIn("[STORY BIBLE]", prompt)
        self.assertIn("[RELEASE POLICY]", prompt)
        self.assertIn("[PLOT OUTLINE]", prompt)
        self.assertIn("next episode", prompt)
```

- [ ] **Step 2: Run the focused prompt-helper tests to verify they fail**

Run: `python3 -m unittest tests.test_context_prompt_sections -v`

Expected: FAIL because `core/context_prompt_sections.py` does not exist yet.

- [ ] **Step 3: Write the minimal prompt helper**

Create `core/context_prompt_sections.py` with:

- `build_worldview_context(worldview: str, tone_and_manner: str) -> str`
- `build_continuity_context(continuity: str) -> str`
- `build_canon_context(canon_state: dict) -> str`
- `build_release_policy_context(release_policy: dict) -> str`
- `build_state_context(state: str, summary_of_previous: str) -> str`
- `build_character_context(characters: list[dict]) -> str`
- `build_plot_block(*, plot_outline: str, include_plot: bool, plot_strength: str) -> str`
- `build_generation_prompt(...) -> str`

Preserve current prompt text as closely as possible, including section labels and length-goal block.

- [ ] **Step 4: Rewire `ContextManager` to delegate prompt assembly and character formatting**

Modify `core/context.py` so that:

- `get_worldview_context()`, `get_continuity_context()`, `get_canon_context()`, `get_release_policy_context()`, `get_state_context()`, `get_character_context()`
  use helper functions
- `build_generation_prompt(...)` delegates final string composition
- remove the dead `if False:` block from `build_generation_prompt(...)`

- [ ] **Step 5: Re-run focused prompt/context regressions**

Run:

```bash
python3 -m unittest \
  tests.test_context_characters \
  tests.test_context_prompt_sections \
  tests.test_context_manager \
  tests.test_reviewer \
  tests.test_token_budget -v
```

Expected: PASS

- [ ] **Step 6: Commit chunk 2**

```bash
git add core/context_characters.py core/context_prompt_sections.py
git add tests/test_context_characters.py tests/test_context_prompt_sections.py
git add core/context.py tests/test_context_manager.py tests/test_reviewer.py
git commit -m "refactor: split context characters and prompt helpers"
```

## Chunk 3: Shrink facade and rebalance context tests

### Task 5: Reduce `ContextManager` to facade-level coordination

**Files:**
- Modify: `core/context.py`
- Modify: `tests/test_context_manager.py`

- [ ] **Step 1: Add failing facade-focused tests if needed**

If the current facade file still relies on helper internals directly, add or update tests to lock:

- `ContextManager` public methods still exist
- structured stores still take precedence over legacy fallback
- helper extraction does not change `get_workspace_settings()` and `build_generation_prompt(...)` outputs

Prefer narrow additions rather than duplicating helper-level assertions.

- [ ] **Step 2: Run the context facade tests to confirm the target behavior**

Run: `python3 -m unittest tests.test_context_manager -v`

Expected: PASS before cleanup edits, giving a stable baseline.

- [ ] **Step 3: Trim `context.py` internals**

Simplify `core/context.py` so it mainly:

- constructs collaborator stores and helper dependencies
- delegates helper behavior
- preserves public facade methods

Remove internal helper methods that are now redundant:

- raw shadow normalization
- state shadow write-through
- character normalization internals
- prompt-string body construction

Keep only small glue helpers where necessary.

- [ ] **Step 4: Rebalance `tests/test_context_manager.py`**

Move pure helper-detail assertions out of `tests/test_context_manager.py` so it keeps only facade-level behavior.

Good candidates to remove from the facade test file after helper coverage exists:

- invalid character filtering details
- shadow payload coercion minutiae
- direct prompt formatting minutiae

Do not reduce coverage; move it to the helper test files created above.

- [ ] **Step 5: Re-run the context-focused suite**

Run:

```bash
python3 -m unittest \
  tests.test_context_story_bible_shadow \
  tests.test_context_state_shadow \
  tests.test_context_characters \
  tests.test_context_prompt_sections \
  tests.test_context_manager -v
```

Expected: PASS

- [ ] **Step 6: Commit chunk 3**

```bash
git add core/context.py
git add tests/test_context_manager.py tests/test_context_story_bible_shadow.py
git add tests/test_context_state_shadow.py tests/test_context_characters.py tests/test_context_prompt_sections.py
git commit -m "refactor: shrink context manager facade"
```

## Chunk 4: Broader regression and cleanup verification

### Task 6: Verify dependent flows still work

**Files:**
- No new files; verification only

- [ ] **Step 1: Run the context-dependent regression suite**

Run:

```bash
python3 -m unittest \
  tests.test_context_story_bible_shadow \
  tests.test_context_state_shadow \
  tests.test_context_characters \
  tests.test_context_prompt_sections \
  tests.test_context_manager \
  tests.test_generator_storage \
  tests.test_chapter_source \
  tests.test_token_budget \
  tests.test_ui_helpers \
  tests.test_reviewer -v
```

Expected: PASS

- [ ] **Step 2: Run syntax verification for touched modules**

Run:

```bash
python3 -m py_compile \
  core/context_story_bible_shadow.py \
  core/context_state_shadow.py \
  core/context_characters.py \
  core/context_prompt_sections.py \
  core/context.py \
  tests/test_context_story_bible_shadow.py \
  tests/test_context_state_shadow.py \
  tests/test_context_characters.py \
  tests/test_context_prompt_sections.py \
  tests/test_context_manager.py
```

Expected: PASS

- [ ] **Step 3: Inspect diff scope**

Run:

```bash
git diff --stat -- \
  core/context.py \
  core/context_story_bible_shadow.py \
  core/context_state_shadow.py \
  core/context_characters.py \
  core/context_prompt_sections.py \
  tests/test_context_manager.py \
  tests/test_context_story_bible_shadow.py \
  tests/test_context_state_shadow.py \
  tests/test_context_characters.py \
  tests/test_context_prompt_sections.py

git diff --check -- \
  core/context.py \
  core/context_story_bible_shadow.py \
  core/context_state_shadow.py \
  core/context_characters.py \
  core/context_prompt_sections.py \
  tests/test_context_manager.py \
  tests/test_context_story_bible_shadow.py \
  tests/test_context_state_shadow.py \
  tests/test_context_characters.py \
  tests/test_context_prompt_sections.py
```

Expected:

- diff stays inside the intended cleanup slice
- no whitespace errors

- [ ] **Step 4: Summarize residual non-goals**

Record explicitly in the execution summary if these remain intentionally untouched:

- UI decomposition for `workspace.py`, `chapters.py`, `publishing.py`
- planner redesign
- removal of all legacy shadow writes
- publishing and marketing feature work

- [ ] **Step 5: No extra commit unless verification forces a fix**

If no verification failure requires additional changes, stop here and hand off to execution.

Plan complete and saved to `docs/superpowers/plans/2026-03-16-context-manager-decomposition-v1.md`. Ready to execute?
