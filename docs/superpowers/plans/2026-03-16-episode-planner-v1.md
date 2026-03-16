# Episode Planner v1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `EpisodePlanner` that generates a structured per-episode plan, feeds that plan into chapter generation, and records planner snapshots for later debugging.

**Architecture:** Keep the current `core/planner.py` untouched for ideation and macro plot work, and add a new `core/episode_planner.py` as the runtime planning boundary. Integrate the planner into `Generator.create_chapter(...)` through an explicit `[EPISODE PLAN]` prompt block, with graceful fallback when planning fails or returns unusable data.

**Tech Stack:** Python, unittest, existing structured stores (`StoryBibleStore`, `CanonStore`, `ContextStateStore`, `PlotStore`, `ReleasePolicyStore`, `PublishingStore`), `core.llm.generate_text`, `RunSnapshotStore`

---

## File Structure

### New files

- `core/episode_planner.py`
  - structured one-episode planning boundary
- `tests/test_episode_planner.py`
  - focused unit tests for planner input/output normalization and LLM usage
- `tests/test_generator_planning.py`
  - generator integration tests for planner prompt block, fallback behavior, and snapshot recording

### Modified files

- `core/generator.py`
  - instantiate and call `EpisodePlanner`, include plan block in generation input, record run snapshots
- `core/context_prompt_sections.py`
  - add optional `[EPISODE PLAN]` block support to prompt composition
- `core/context.py`
  - pass the optional planner block through the public prompt-building facade
- `tests/test_planner.py`
  - leave legacy ideation coverage intact; add only if names or imports shift
- `tests/test_generator_storage.py`
  - update only if generator constructor or snapshot side effects change storage expectations

### Existing files to reference

- `core/planner.py`
- `core/context.py`
- `core/context_prompt_sections.py`
- `core/story_bible_store.py`
- `core/canon_store.py`
- `core/context_state_store.py`
- `core/plot_store.py`
- `core/release_policy_store.py`
- `core/publishing_store.py`
- `core/run_snapshot_store.py`
- `core/llm.py`

## Chunk 1: Add the EpisodePlanner core

### Task 1: Create focused planner tests first

**Files:**
- Create: `tests/test_episode_planner.py`
- Create: `core/episode_planner.py`

- [ ] **Step 1: Write the failing planner tests**

Create `tests/test_episode_planner.py` with cases like:

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.canon_store as canon_store_module
import core.context_state_store as context_state_store_module
import core.plot_store as plot_store_module
import core.publishing_store as publishing_store_module
import core.release_policy_store as release_policy_store_module
import core.story_bible_store as story_bible_store_module
from core.canon_store import CanonStore
from core.context_state_store import ContextStateStore
from core.episode_planner import EpisodePlanner
from core.plot_store import PlotStore
from core.publishing_store import PublishingStore
from core.release_policy_store import ReleasePolicyStore
from core.story_bible_store import StoryBibleStore


class TestEpisodePlanner(unittest.TestCase):
    def test_build_episode_plan_passes_project_and_feature_to_generate_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            with patch.object(story_bible_store_module, "DATA_PROJECTS_DIR", base), \
                 patch.object(canon_store_module, "DATA_PROJECTS_DIR", base), \
                 patch.object(context_state_store_module, "DATA_PROJECTS_DIR", base), \
                 patch.object(plot_store_module, "DATA_PROJECTS_DIR", base), \
                 patch.object(release_policy_store_module, "DATA_PROJECTS_DIR", base), \
                 patch.object(publishing_store_module, "DATA_PROJECTS_DIR", base):
                StoryBibleStore("sample").save(
                    {
                        "worldview": "도시 판타지",
                        "style_guide": "긴장 유지",
                        "fixed_rules": "설정 충돌 금지",
                        "author_intent": "",
                    }
                )
                CanonStore("sample").save_current_state({"people": {}, "resources": {}, "hooks": [], "timeline": []})
                ContextStateStore("sample").save({"state": "추격 직후", "summary_of_previous": "주인공이 계약서를 훔쳤다."})
                ReleasePolicyStore("sample").save({"global": {"max_daily_releases": 1, "burst_allowed": False}, "platforms": {}})
                PublishingStore("sample").append_history({"timestamp": "2026-03-16T00:00:00+00:00", "success": True})

                planner = EpisodePlanner(project_name="sample")
                with patch("core.episode_planner.generate_text", return_value='{\"episode_objective\": \"추적을 피하고 단서를 확보\", \"must_include_characters\": [\"lead\"], \"hooks_to_payoff\": [], \"hooks_to_advance\": [\"계약서 비밀\"], \"forbidden_moves\": [\"새 설정 추가 금지\"], \"target_length\": 5000, \"tone_notes\": \"긴장 유지\", \"continuity_focus\": [\"도주 직후 상태 유지\"], \"plan_version\": \"v1\"}') as mocked_generate:
                    result = planner.build_episode_plan("다음 화를 써줘", length_goal=5000, include_plot=False)

                self.assertEqual(result["plan_version"], "v1")
                self.assertEqual(mocked_generate.call_args.kwargs["feature"], "episode_plan")
                self.assertEqual(mocked_generate.call_args.kwargs["project_name"], "sample")

    def test_build_episode_plan_normalizes_missing_fields_to_defaults(self):
        ...

    def test_build_episode_plan_omits_plot_input_when_disabled(self):
        ...

    def test_build_episode_plan_uses_empty_plan_when_model_output_is_not_json(self):
        ...
```

- [ ] **Step 2: Run the focused planner tests to verify they fail**

Run: `python3 -m unittest tests.test_episode_planner -v`

Expected: FAIL because `core/episode_planner.py` does not exist yet.

- [ ] **Step 3: Write the minimal `EpisodePlanner`**

Create `core/episode_planner.py` with:

- `DEFAULT_EPISODE_PLAN`
- `EpisodePlanner.__init__(project_name: str, ...)`
- `_build_planner_prompt(...)`
- `_normalize_plan_payload(payload: dict | list | None, *, length_goal: int) -> dict`
- `build_episode_plan(instruction: str, *, length_goal: int, include_plot: bool, plot_strength: str = "balanced") -> dict`

Implementation rules:

- read from `StoryBibleStore`, `CanonStore`, `ContextStateStore`, `ReleasePolicyStore`
- read recent history through `PublishingStore.load_recent_history(...)`
- read `PlotStore` only when `include_plot=True`
- parse planner output with `core.llm._extract_first_json_value`
- always return a normalized dict with required keys
- never mutate stores

- [ ] **Step 4: Re-run the focused planner tests**

Run: `python3 -m unittest tests.test_episode_planner -v`

Expected: PASS

- [ ] **Step 5: Commit chunk 1**

```bash
git add core/episode_planner.py tests/test_episode_planner.py
git commit -m "feat: add episode planner core"
```

## Chunk 2: Integrate planner output into generation prompts

### Task 2: Add generator integration tests first

**Files:**
- Create: `tests/test_generator_planning.py`
- Modify: `core/generator.py`
- Modify: `core/context_prompt_sections.py`
- Modify: `core/context.py`

- [ ] **Step 1: Write the failing generator planning tests**

Create `tests/test_generator_planning.py` with cases like:

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.context as context_module
from core.generator import Generator


class TestGeneratorPlanning(unittest.TestCase):
    def test_create_chapter_includes_episode_plan_block_when_planner_returns_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(context_module, "BASE_DATA_DIR", Path(tmpdir)):
                generator = Generator(project_name="sample")
                with patch.object(generator.episode_planner, "build_episode_plan", return_value={
                    "episode_objective": "탈출 후 은신처 확보",
                    "must_include_characters": ["lead"],
                    "hooks_to_payoff": [],
                    "hooks_to_advance": ["계약서 비밀"],
                    "forbidden_moves": ["새 설정 추가 금지"],
                    "target_length": 5000,
                    "tone_notes": "긴장 유지",
                    "continuity_focus": ["추격 직후 상태 유지"],
                    "plan_version": "v1",
                }), patch("core.generator.generate_text", return_value="chapter body") as mocked_generate:
                    generator.create_chapter("다음 화를 써줘", length_goal=5000)

                prompt = mocked_generate.call_args.args[0]
                self.assertIn("[EPISODE PLAN]", prompt)
                self.assertIn("탈출 후 은신처 확보", prompt)

    def test_create_chapter_falls_back_when_planner_returns_empty_plan(self):
        ...

    def test_create_chapter_passes_plot_flag_into_episode_planner(self):
        ...
```

- [ ] **Step 2: Run the focused generator planning tests to verify they fail**

Run: `python3 -m unittest tests.test_generator_planning -v`

Expected: FAIL because generator does not use an `EpisodePlanner` yet.

- [ ] **Step 3: Add planner block support to prompt assembly**

Modify `core/context_prompt_sections.py`:

- extend `build_generation_prompt(...)` to accept `episode_plan_block: str = ""`
- inject the block between state context and character context

Add a helper:

```python
def build_episode_plan_block(plan_payload: dict) -> str:
    ...
```

Block format:

```text
[EPISODE PLAN]
- episode_objective: ...
- must_include_characters: ...
- hooks_to_payoff: ...
- hooks_to_advance: ...
- forbidden_moves: ...
- target_length: ...
- tone_notes: ...
- continuity_focus: ...
```

- [ ] **Step 4: Pass the new planner block through `ContextManager`**

Modify `core/context.py` so `build_generation_prompt(...)` accepts:

- `episode_plan_block: str = ""`

and forwards it to `core.context_prompt_sections.build_generation_prompt(...)`.

Do not move planner logic into `ContextManager`.

- [ ] **Step 5: Integrate `EpisodePlanner` into `Generator.create_chapter(...)`**

Modify `core/generator.py` so that:

- `Generator.__init__` constructs `self.episode_planner = EpisodePlanner(project_name=project_name)`
- `create_chapter(...)` calls `self.episode_planner.build_episode_plan(...)`
- the resulting plan is converted to an `[EPISODE PLAN]` block
- the block is passed into `self.ctx.build_generation_prompt(...)`
- if planner output is empty or malformed, generation still proceeds without the block

- [ ] **Step 6: Re-run the focused generator planning tests**

Run: `python3 -m unittest tests.test_generator_planning tests.test_episode_planner -v`

Expected: PASS

- [ ] **Step 7: Commit chunk 2**

```bash
git add core/episode_planner.py core/generator.py core/context.py core/context_prompt_sections.py
git add tests/test_episode_planner.py tests/test_generator_planning.py
git commit -m "feat: route generation through episode planner"
```

## Chunk 3: Add planner snapshots and fallback coverage

### Task 3: Record planner snapshots for generated chapters

**Files:**
- Modify: `core/generator.py`
- Modify: `tests/test_generator_planning.py`

- [ ] **Step 1: Add failing snapshot tests**

Extend `tests/test_generator_planning.py` with cases like:

```python
def test_create_chapter_writes_episode_plan_snapshot(self):
    ...

def test_create_chapter_writes_empty_plan_snapshot_when_planner_fails(self):
    ...
```

Assert:

- a generation run directory is created under `runs/`
- `episode_plan.json` exists
- planner failure still allows chapter generation and records an explicit empty/fallback plan payload

- [ ] **Step 2: Run the snapshot-focused tests to verify they fail**

Run: `python3 -m unittest tests.test_generator_planning -v`

Expected: FAIL because generator does not write planner snapshots yet.

- [ ] **Step 3: Add planner snapshot recording**

Modify `core/generator.py`:

- instantiate `RunSnapshotStore(project_name=project_name)`
- create a generation run id such as `chapter`
- write `episode_plan.json` before the model call
- optionally write `generation_prompt.txt` only if needed for existing patterns; do not expand scope unless tests require it

Planner failure behavior:

- catch planner exceptions inside `create_chapter(...)`
- record a fallback plan payload with:
  - `episode_objective: ""`
  - required list fields empty
  - `target_length` from input
  - `plan_version: "v1"`
  - `planner_error: "<message>"`
- continue generation

- [ ] **Step 4: Re-run the focused generator planning tests**

Run: `python3 -m unittest tests.test_generator_planning tests.test_generator_storage -v`

Expected: PASS

- [ ] **Step 5: Commit chunk 3**

```bash
git add core/generator.py tests/test_generator_planning.py tests/test_generator_storage.py
git commit -m "feat: persist episode planner snapshots"
```

## Chunk 4: Regression and boundary verification

### Task 4: Run broader planner/generator regressions

**Files:**
- No new files; verification only

- [ ] **Step 1: Run the focused planner/generator suite**

Run:

```bash
python3 -m unittest \
  tests.test_episode_planner \
  tests.test_generator_planning \
  tests.test_planner \
  tests.test_context_manager \
  tests.test_generator_storage \
  tests.test_token_budget \
  tests.test_reviewer -v
```

Expected: PASS

- [ ] **Step 2: Run the broader origin/publishing regression suite**

Run:

```bash
python3 -m unittest \
  tests.test_story_bible_store \
  tests.test_context_state_store \
  tests.test_plot_store \
  tests.test_canon_store \
  tests.test_release_policy_store \
  tests.test_episode_artifact_store \
  tests.test_run_snapshot_store \
  tests.test_origin_quality \
  tests.test_context_manager \
  tests.test_generator_storage \
  tests.test_generator_planning \
  tests.test_chapter_source \
  tests.test_automation_store \
  tests.test_automation_runtime \
  tests.test_automation_ui \
  tests.test_diagnostics_ui \
  tests.test_automator \
  tests.test_canon_extractor \
  tests.test_publishing_executor \
  tests.test_release_policy_engine \
  tests.test_publishing_policy \
  tests.test_publishing_runtime \
  tests.test_publishing_structure \
  tests.test_quality_gate_orchestrator \
  tests.test_publishing_quality \
  tests.test_publishing_incidents \
  tests.test_publishing_canon \
  tests.test_token_budget \
  tests.test_ui_helpers \
  tests.test_reviewer \
  tests.test_planner \
  tests.test_episode_planner -v
```

Expected: PASS

- [ ] **Step 3: Run syntax verification**

Run:

```bash
python3 -m py_compile \
  core/episode_planner.py \
  core/generator.py \
  core/context.py \
  core/context_prompt_sections.py \
  tests/test_episode_planner.py \
  tests/test_generator_planning.py
```

Expected: PASS

- [ ] **Step 4: Inspect diff scope**

Run:

```bash
git diff --stat -- \
  core/episode_planner.py \
  core/generator.py \
  core/context.py \
  core/context_prompt_sections.py \
  tests/test_episode_planner.py \
  tests/test_generator_planning.py \
  tests/test_generator_storage.py

git diff --check -- \
  core/episode_planner.py \
  core/generator.py \
  core/context.py \
  core/context_prompt_sections.py \
  tests/test_episode_planner.py \
  tests/test_generator_planning.py \
  tests/test_generator_storage.py
```

Expected:

- diff stays inside the intended planner/generator slice
- no whitespace errors

- [ ] **Step 5: Summarize residual non-goals**

Record explicitly in the execution summary if these remain intentionally untouched:

- replacement of legacy `core/planner.py`
- critic LLM gate
- marketing packager
- locale pipeline
- multi-episode planning
- long-arc plot redesign

- [ ] **Step 6: No extra commit unless verification forces a fix**

If verification remains green after the last commit, stop here and hand off to execution.
