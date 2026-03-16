# Critic Gate V1 Design

## Goal

Add a final LLM-based critic gate after the existing cheap quality passes so `_2` can block structurally valid but narratively weak publish candidates before platform upload.

## Context

`_2` now has:

- structured episode planning via `EpisodePlanner`
- cheap publish validation via rules, structure, and one-shot repair
- publish control plane v1 with policy, incidents, and canon finalize

The remaining gap inside the top-level design is a final narrative-quality stop layer. The current `QualityGateOrchestrator` can reject obvious malformed drafts, but it cannot judge whether a draft actually follows the episode plan, preserves recent continuity, or still reads like a publish-ready chapter.

## Scope

This slice adds:

- a dedicated `publishing_critic` module
- critic execution only after rules/structure/repair already pass
- critic result integration into `QualityGateOrchestrator`
- critic-aware runtime blocking and snapshot persistence

This slice does not add:

- critic-generated repair instructions
- multi-pass rewrite loops
- episode re-generation
- platform-specific critic criteria
- marketing or locale pipeline work

## Recommended Approach

### Option A: Inline critic call inside `publishing_runtime`

Pros:

- fastest to wire

Cons:

- repeats the same mistake the recent refactors were undoing
- mixes LLM quality policy into runtime coordination
- makes later critic evolution harder

### Option B: Add `publishing_critic.py` and call it from `quality_gate_orchestrator`

Pros:

- keeps runtime as coordinator only
- keeps the expensive LLM gate isolated
- matches the top-level design's `Quality Gate Orchestrator` responsibility
- gives a clean seam for future critic tuning

Cons:

- introduces one more focused module and test boundary

### Option C: Let critic also generate repair instructions

Pros:

- could support automatic narrative repair later

Cons:

- larger surface area
- higher cost and more unstable behavior
- expands this slice beyond v1

## Recommendation

Choose Option B.

Critic v1 should be a binary stop layer with a short report. It should not repair, retry, or regenerate.

## Architecture

### `core/publishing_critic.py`

Responsibility:

- evaluate a publish-ready draft with one LLM pass
- normalize the result into a stable machine-readable report

Input:

- `final_source`
- `episode_plan`
- optional lightweight context fields such as release policy or state snapshot

Output:

```json
{
  "status": "passed|blocked|critic_unavailable",
  "summary": "short critic verdict",
  "issues": ["..."],
  "model": "gemini-2.5-flash",
  "cost": {"mode": "single_pass"},
  "raw_excerpt": "truncated raw response"
}
```

### `core/quality_gate_orchestrator.py`

Responsibility changes:

- keep `rules -> structure -> optional repair`
- call critic once only if the draft is publishable after cheap gates
- translate critic failure into final `hard_fail`

### `core/publishing_runtime.py`

Responsibility changes:

- continue treating the orchestrator as the single quality boundary
- persist critic-inclusive `quality_report.json`
- block executor calls when critic does not pass

Runtime should not know critic prompt details.

## Decision Rules

### `passed`

The critic sees no publish-blocking issue. The orchestrator returns final `publishable`.

### `blocked`

The critic finds a narrative or continuity problem severe enough that the chapter should not publish.

Typical examples:

- episode objective is missing or clearly not executed
- forbidden move in the episode plan is violated
- recent continuity or state is contradicted
- publishable text still reads like a draft or outline
- chapter hook/completion quality is too weak to publish

The orchestrator converts this into final `hard_fail`.

### `critic_unavailable`

The critic model fails operationally:

- timeout
- backend error
- unparsable output

In v1 this still blocks publish. The runtime should distinguish it from content failure in the saved report, but should not auto-pass.

## Data Flow

1. `PublishingRuntime.tick()` loads source.
2. `QualityGateOrchestrator` runs cheap rules and structure checks.
3. If needed, one repair pass runs.
4. Only if the repaired or original draft is publishable does `publishing_critic` run.
5. Critic `passed` returns final `publishable`.
6. Critic `blocked` or `critic_unavailable` returns final `hard_fail`.
7. Runtime records the critic-inclusive quality report and does not call executor on failure.

## Testing

### New tests

- `tests/test_publishing_critic.py`
  - normalizes `passed`
  - normalizes `blocked`
  - returns `critic_unavailable` on backend failure
  - returns `critic_unavailable` on bad JSON

### Updated tests

- `tests/test_quality_gate_orchestrator.py`
  - critic only runs after cheap gates pass
  - critic `blocked` becomes final `hard_fail`
  - critic `critic_unavailable` becomes final `hard_fail`

- `tests/test_publishing_runtime.py`
  - executor is skipped when critic blocks
  - `quality_report.json` includes `critic`

## Non-goals

- automatic narrative repair
- critic retry loops
- critic-specific policy ledger
- planner-aware scoring beyond binary gating
- marketing, translation, or overseas publishing

## Result

This slice closes the most important quality gap left after `Episode Planner v1` and `Quality Gate Orchestrator v1`: a final narrative-quality stop layer before platform upload.
