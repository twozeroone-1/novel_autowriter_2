# Quality Gate Regenerate-Once V1 Design

## Goal

Fill the remaining `Gate 4` gap from the top-level fully automated serialization design by allowing exactly one full chapter regeneration after a publish candidate fails narrative quality checks.

This slice keeps the existing `episode_plan` fixed. It does not rewrite planning, add multi-pass loops, or let runtime own generation retry policy.

## Context

`_2` already has:

- structured `Episode Planner v1`
- cheap rule and structure gates
- one-shot low-cost repair
- final critic gate

Current flow:

`rules -> structure -> optional repair -> critic -> publish/block`

The remaining top-level gap is that a chapter can still fail for narrative reasons that are not cheaply repairable, but the system has no bounded full-regeneration path before declaring final failure.

The higher-level design explicitly requires:

- one low-cost repair for rule-only issues
- one full regeneration for structure or critic failures
- then hard stop

## Scope

This slice adds:

- a dedicated regeneration helper boundary
- one regeneration attempt using the same `episode_plan`
- regenerate-aware orchestration inside `quality_gate_orchestrator`
- regenerate details in the persisted quality report

This slice intentionally does not add:

- new planner generation
- multi-pass regeneration loops
- critic-generated rewrite instructions
- runtime-owned generation retry policy
- marketing or locale behavior

## Options

### Option A: Put regeneration directly inside `quality_gate_orchestrator`

Pros:

- fastest to ship
- minimal surface area

Cons:

- makes the orchestrator own generation mechanics
- increases coupling to `Generator`
- harder to swap regeneration policy later

### Option B: Add a dedicated `publishing_regenerate.py` helper and let the orchestrator call it

Pros:

- clean boundary between quality policy and generation mechanics
- easier to test with injected regenerate functions
- matches the existing separation between `repair`, `critic`, and runtime coordination

Cons:

- adds one more module

### Option C: Let `publishing_runtime` own regeneration

Pros:

- keeps the orchestrator purely evaluative

Cons:

- pushes quality business logic back into runtime
- weakens the boundaries introduced by publish control plane work
- makes future retry policy harder to reason about

## Recommendation

Use **Option B**.

Keep regeneration as a bounded helper that the orchestrator may call once, while runtime continues to consume only the final orchestrator verdict.

## Architecture

### `core/publishing_regenerate.py`

Add a narrow helper boundary:

- `regenerate_publish_source(source_payload: dict, *, episode_plan: dict | None, project_name: str | None = None, length_goal: int | None = None) -> dict`

Responsibilities:

- build a regeneration prompt using the same `episode_plan`
- preserve the current episode identity and metadata
- return a normalized source candidate:
  - `title`
  - `content`
  - `regeneration_summary`

The helper should not mutate Canon, artifacts, or runtime state.

### `core/quality_gate_orchestrator.py`

Keep it as the single quality decision boundary.

New responsibilities:

- determine whether a final failure is regenerateable
- call regeneration at most once
- re-run the same cheap gates and critic on the regenerated candidate
- produce a final report that includes:
  - initial evaluation
  - repair attempt, if any
  - regeneration attempt, if any
  - regenerated evaluation

The orchestrator should accept an injectable `regenerate_fn` for tests.

### `core/publishing_runtime.py`

Runtime should not gain new retry policy logic.

It should continue to:

- pass source plus `episode_plan` into the orchestrator
- obey only the final orchestrator result
- persist the richer quality report into `quality_report.json`

## Decision Rules

### Repair remains unchanged

- `retry_possible` from cheap rules or structure -> one repair attempt
- if repair succeeds -> continue
- if repair still fails -> continue to regenerateability check

### When regeneration is allowed

Allow exactly one full regeneration only for bounded narrative-quality failures:

- critic returned `blocked`
- structure failure is judged regenerateable

V1 regenerateable structure failures should be limited to cases where the chapter is chapter-shaped but weak:

- missing meaningful event progression
- weak or absent conflict/change signal
- episode shape exists but the scene outcome is structurally empty

### When regeneration is not allowed

Do **not** regenerate for:

- episode number mismatch
- missing or near-empty body
- draft/report marker contamination
- malformed or missing title
- explicit data-integrity failures
- critic operational failure such as `critic_unavailable`

These are input or operational failures, not valid narrative retry candidates.

### Regeneration budget

Hard upper bound:

- repair: at most 1
- regenerate: at most 1

If the regenerated candidate still does not pass, final status is `hard_fail`.

## Data Flow

1. Runtime loads source and `episode_plan`.
2. Orchestrator runs cheap rules and structure checks.
3. If needed and recoverable, repair runs once.
4. Critic runs only after a publishable candidate exists.
5. If the result is final `publishable`, orchestration ends.
6. If the result is `hard_fail`, orchestrator classifies the failure as regenerateable or not.
7. If regenerateable, the orchestrator calls `regenerate_publish_source(...)` once using the same `episode_plan`.
8. The regenerated candidate is re-evaluated with:
   - cheap rules
   - structure
   - critic
9. If regenerated output passes, final status becomes `publishable`.
10. Otherwise final status remains `hard_fail`.

Runtime still sees only:

- `publishable`
- `hard_fail`

## Reporting

`quality_report.json` should preserve enough detail to explain what happened:

```json
{
  "status": "publishable|hard_fail",
  "attempted_repair": true,
  "attempted_regenerate": true,
  "regeneration_summary": {
    "status": "applied|failed|skipped",
    "reason": "critic blocked publish"
  },
  "gate_reports": {
    "initial": { "...": "..." },
    "final": { "...": "..." },
    "regenerated": { "...": "..." }
  }
}
```

Exact field names may vary slightly, but the report must distinguish:

- pre-repair state
- post-repair state
- regenerated state

## Testing

### `tests/test_publishing_regenerate.py`

Cover:

- helper reuses the provided `episode_plan`
- helper returns normalized title/content output
- helper converts LLM/backend exceptions into a bounded failure payload or raised typed error expected by the orchestrator

### `tests/test_quality_gate_orchestrator.py`

Cover:

- critic-blocked candidate regenerates once and then passes
- regenerateable structure failure regenerates once
- non-regenerateable hard fail skips regeneration
- regenerated candidate that still fails returns final `hard_fail`
- regeneration is attempted at most once

### `tests/test_publishing_runtime.py`

Cover:

- runtime still only consumes final orchestrator verdicts
- executor is skipped on final `hard_fail`
- `quality_report.json` persists regenerate-aware details

## Non-goals

- replanning the episode
- critic-directed rewrite instructions
- two or more regeneration loops
- reserved publish support
- marketing generation
- locale pipeline behavior

## Result

This slice completes the missing top-level `Gate 4` behavior without reopening large architectural boundaries.

The system becomes:

- strict about input/data failures
- bounded in cost
- more resilient to one-off narrative misfires
- still deterministic enough for automated publishing control
