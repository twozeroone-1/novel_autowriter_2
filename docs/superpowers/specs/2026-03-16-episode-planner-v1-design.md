# Episode Planner v1 Design

## Background

`_2` now has most of the storage and publish-control boundaries required by the higher-level serialization design:

- `Story Bible`, `Canon DB`, `ContextStateStore`, `PlotStore`, and release-policy storage exist.
- publishing now runs through release-policy evaluation and a real `Quality Gate Orchestrator v1`.
- Canon finalize happens only after successful publication.

What is still missing from the higher-level design is the front half of the episode pipeline:

- there is no dedicated `Episode Planner`
- generation still depends on large freeform context blocks and optional plot text
- the current `core/planner.py` is not an episode planner at all

Today `core/planner.py` does two different jobs:

- high-level idea suggestion
- long-form macro plot drafting

Those are useful, but they are not the structured per-episode planning boundary described in the top-level design. If we keep calling that module “planner” without adding a real episode planner, the system will continue to rely on loose instructions and prompt bloat instead of deterministic planning data.

That matters because the system goals are now constrained by:

- quality stability
- lower token cost
- safer fully automatic operation

Without a structured planner output, the Draft Writer cannot be constrained tightly enough, and the Quality Gate has to catch more failures later than it should.

## Goal

Add an `Episode Planner v1` that produces a narrow structured plan for one episode before draft generation.

This v1 should:

- read from existing structured stores
- create a stable per-episode planning payload
- reduce dependence on freeform “just write the next chapter” instructions
- give the Draft Writer a smaller, more explicit input contract

It should not yet attempt full literary reasoning, critic feedback, or long-arc optimization.

## Why This Slice

The higher-level implementation order calls out:

1. `Story Bible / Canon DB / Run Snapshot`
2. `Episode Planner / Draft Writer / Quality Gate Orchestrator`
3. `Publish Packager / platform adapters`
4. `Release Policy Engine and incident-driven runtime state`

`_2` is already past step 1, has significant parts of step 3, and now has the quality side of step 2.

The weakest remaining gap is the missing `Episode Planner`. Until that exists, the system still jumps from broad context directly into chapter generation.

This spec closes the planner half of step 2 without trying to redesign the full generator stack at once.

## Approaches

### Option 1. Extend the existing `core/planner.py`

Add per-episode planning methods to the current `Planner` class.

Pros:

- fewer files
- faster initial diff

Cons:

- keeps one name covering unrelated jobs
- mixes ideation, macro plot, and runtime episode planning
- makes future replacement harder

### Option 2. Add a dedicated `core/episode_planner.py`

Keep the current `Planner` for ideation and macro plot work, and add a separate `EpisodePlanner` for runtime chapter planning.

Pros:

- matches the top-level design directly
- avoids semantic confusion around “planner”
- gives Draft Writer a clean, testable input boundary

Cons:

- adds one more module now

### Option 3. Skip a planner module and inject a JSON planning block directly in `ContextManager`

Build a planning payload inline during prompt assembly without a standalone planner abstraction.

Pros:

- smallest short-term code change

Cons:

- repeats the same mistake already being removed elsewhere
- keeps planning logic buried inside prompt construction
- makes testing and later extension awkward

This spec chooses option 2.

## Scope

### In scope

- new `core/episode_planner.py`
- structured plan generation for one episode
- plan payload derived from `Story Bible`, `Canon DB`, `Release Policy`, current workspace state, and recent publish history
- a new prompt block consumed by Draft Writer
- unit tests for planner output and integration points

### Out of scope

- replacing the current `core/planner.py`
- redesigning long-range plot tooling
- critic model integration
- multi-episode planning
- marketing generation
- locale pipeline
- automatic genre trend optimization

## Proposed Architecture

### New module: `core/episode_planner.py`

This module owns the answer to:

`What should this specific episode try to do, in a structured way, before writing begins?`

It should be independent of publishing runtime and independent of UI-specific state.

### Existing modules after this change

- `core/planner.py`
  - remains ideation and macro-plot tooling only
- `core/episode_planner.py`
  - creates the structured episode plan
- `core/generator.py`
  - uses planner output as the primary chapter-writing plan input
- `core/context.py`
  - continues to provide store-backed context, but no longer has to carry the whole burden of “what this episode is for”

## Episode Planner Input Contract

`EpisodePlanner` should read only structured or bounded inputs:

- `Story Bible`
  - worldview
  - style guide
  - fixed rules
- `Canon DB`
  - people
  - resources
  - hooks
  - timeline
- `Release Policy`
  - only coarse cadence constraints relevant to pacing
- current workspace state
  - `state`
  - `summary_of_previous`
- optional plot outline
  - only when the caller explicitly requests plot guidance
- recent publish history
  - for cadence-sensitive planning, not narrative truth

The key rule is that `Episode Planner` reads these inputs but does not mutate them.

## Episode Planner Output Contract

The planner should return a normalized payload like:

```python
{
    "episode_objective": "이번 화에서 반드시 달성할 핵심 서사 목적",
    "must_include_characters": ["lead", "rival"],
    "hooks_to_payoff": ["contract clue"],
    "hooks_to_advance": ["sponsor mystery"],
    "forbidden_moves": [
        "새 세계관 규칙 추가 금지",
        "주인공의 목표를 갑자기 바꾸지 말 것",
    ],
    "target_length": 5000,
    "tone_notes": "긴장 유지, 과장 개그 절제",
    "continuity_focus": [
        "지난 화의 탈출 직후 상황 유지",
        "조연 반응은 과잉 해설로 흐르지 않기",
    ],
    "plan_version": "v1"
}
```

The exact keys can still be adjusted during implementation, but v1 must at least cover the high-level fields promised by the top-level design:

- episode goal
- participating characters
- hooks to resolve or advance
- forbidden moves
- expected length

## Planner Prompt Strategy

The planner should be cheaper and more structured than chapter generation.

Recommended prompt shape:

- short system instruction focused on planning, not prose writing
- structured input blocks from stores
- explicit JSON-only output contract
- explicit instruction to avoid inventing new canon facts

This stage is not the place to write polished prose. It is a constrained planning task.

That matters for cost control:

- planning should use fewer tokens than draft generation
- the planner output should shrink the later Draft Writer prompt
- the planner output should be serializable and snapshot-friendly

## Draft Writer Integration

`Generator.create_chapter(...)` should gain a path that:

1. obtains an `episode_plan`
2. writes the plan into the generation prompt in a dedicated `[EPISODE PLAN]` block
3. prefers the plan for episode intent instead of relying on long freeform instructions alone

This does not require fully removing existing context blocks in v1.

Instead, v1 should rebalance the prompt:

- `Story Bible` and `Canon facts` remain reference context
- `Episode Plan` becomes the immediate writing target
- plot outline stays optional

## Persistence and Snapshots

The episode plan should be snapshot-friendly from day one.

At minimum, the plan should be written into run artifacts during generation so that later failures can be explained in terms of:

- what the planner asked for
- what the Draft Writer produced
- what the Quality Gate rejected

This does not require a new permanent store yet. A run snapshot is enough for v1.

## Testing Strategy

### Unit tests

- planner returns a normalized payload with required keys
- planner passes `project_name` and a dedicated planner feature to `generate_text(...)`
- planner gracefully normalizes malformed JSON from the model into a failure or empty-plan result
- planner reads from structured stores, not legacy freeform aliases

### Integration tests

- generator includes `[EPISODE PLAN]` when planner output exists
- generator still works when planner is disabled or returns no usable plan
- run snapshots include the plan payload for generated chapters

### Regression focus

- do not break existing ideation and macro-plot methods in `core/planner.py`
- do not increase prompt coupling back into `ContextManager`

## Risks

### Risk 1. Planner output becomes another large freeform blob

If the planner returns essay-like text, the Draft Writer prompt does not actually improve.

Mitigation:

- JSON-only planner output
- narrow required fields
- tests that enforce a normalized dict contract

### Risk 2. Planner invents canon and contaminates generation

If the planner starts adding “facts” rather than constraints, it becomes a hidden canon source.

Mitigation:

- planner output is guidance only
- Canon DB is still updated only by the publish-success path
- prompts explicitly forbid inventing canonical facts

### Risk 3. Planner and current plot tooling get conflated

If callers keep using `core/planner.py` for unrelated runtime planning, the boundary stays muddy.

Mitigation:

- add a new dedicated `EpisodePlanner`
- leave the old `Planner` in place and treat migration separately

## Non-goals for This Slice

- replacing or deleting `core/planner.py`
- planner-aware literary criticism
- automatic multi-episode batching
- automatic trope optimization from live market data
- a new permanent planner artifact store

## Expected Outcome

After this slice:

- the system has a real `Episode Planner` boundary
- draft generation is guided by structured episode intent, not only broad context
- quality gating receives drafts that were produced against a narrower target
- later work on critic gates and marketing can depend on a cleaner episode contract

This makes the next missing pieces much more straightforward:

- `Episode Planner` hardening
- `Draft Writer` prompt simplification
- eventual critic-gate integration
