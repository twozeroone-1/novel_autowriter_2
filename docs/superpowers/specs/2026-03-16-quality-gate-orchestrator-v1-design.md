# Quality Gate Orchestrator v1 Design

## Background

`_2` already has the first cuts of publishing quality, incident handling, and release policy:

- `core/publishing_quality.py` runs a cheap publishability check from `origin_quality`.
- `core/publishing_runtime.py` calls that check directly before the executor.
- `core/publishing_incidents.py` and the new release policy engine now control runtime state around publish attempts.

What is still missing from the higher-level system design is the actual `Quality Gate Orchestrator`.

Right now the runtime can answer only a binary question:

`is this source immediately publishable or not?`

That is too narrow for the v1 goals. The top-level design expects a quality layer that can:

- separate cheap structural failures from truly unrecoverable failures
- allow one controlled low-cost repair pass
- keep runtime logic out of the details of gate sequencing
- produce a traceable gate report instead of a single flat quality result

Without that boundary, `PublishingRuntime` keeps absorbing quality logic the same way it previously absorbed policy logic.

## Goal

Add a minimal but real `Quality Gate Orchestrator v1` that evaluates a publish source through:

1. cheap rule validation
2. cheap structure validation
3. at most one low-cost repair attempt for recoverable failures
4. final publish-or-block decision

This stage should improve quality stability without yet introducing a critic LLM pass, multi-step rewrite loops, or full episode re-generation.

## Why This Slice

The higher-level implementation order says the next missing capability after the current publish control plane is the unfinished part of:

1. `Episode Planner / Draft Writer / Quality Gate Orchestrator`
2. `Publish Packager / platform adapter integration`
3. `Release Policy Engine and incident-driven runtime state`

`_2` already has:

- storage boundaries for publishable and published episode artifacts
- a publish control plane
- release policy evaluation
- incident summarization and Canon finalize

The weakest remaining v1 gap is still quality orchestration. Marketing and locale are explicitly later-stage work, while quality gating is directly tied to the user’s primary requirement: `품질 안정성 및 비용 절감`.

## Approaches

### Option 1. Keep extending `publishing_runtime.py`

Add rule checks, structure checks, repair calls, and retry logic directly inside the runtime.

Pros:

- quickest short-term change
- minimal file creation

Cons:

- puts sequencing details back into the runtime
- makes later critic-gate work harder
- recreates the oversized coordinator problem that the current refactors are trying to undo

### Option 2. Add a dedicated `quality_gate_orchestrator.py`

Create a separate orchestrator that owns gate sequencing and repair flow, while keeping `publishing_runtime.py` as a coordinator.

Pros:

- matches the top-level design directly
- keeps gate sequencing in one place
- makes future critic-gate and planner-aware checks easier to add

Cons:

- slightly larger change now

### Option 3. Add separate validators only and keep sequencing in runtime

Create `publishing_structure.py` and maybe `publishing_repair.py`, but leave the final decision flow in runtime.

Pros:

- some file decomposition
- smaller initial diff

Cons:

- decision logic still remains split across modules
- `retry_possible` semantics become harder to reason about
- future changes still require runtime rewiring

This spec chooses option 2.

## Scope

### In scope

- new `QualityGateOrchestrator` module
- cheap rule validation reuse from `publishing_quality`
- new cheap structure validator
- single repair attempt for recoverable failures
- final normalized decision contract
- runtime integration with executor gating
- run snapshot quality reporting
- tests for orchestrator and runtime integration

### Out of scope

- critic LLM gate
- episode re-generation
- more than one repair attempt
- global cost ledger redesign
- marketing generation
- locale pipeline
- replacement of the current `Planner` module

## Proposed Architecture

### New modules

- `core/quality_gate_orchestrator.py`
  - owns gate sequencing and final decision
- `core/publishing_structure.py`
  - owns cheap structure-specific validation
- optionally `core/publishing_repair.py`
  - if the repair prompt path needs its own isolated helper

### Existing modules after this change

- `core/publishing_quality.py`
  - remains the cheap rule validator
- `core/publishing_runtime.py`
  - loads source, calls orchestrator, then either blocks or continues to executor
- `core/publishing_incidents.py`
  - remains post-executor incident summarization only

This keeps pre-publish quality sequencing separate from post-publish incident handling.

## Decision Contract

The orchestrator should return a normalized result like:

```python
{
    "status": "publishable" | "hard_fail",
    "attempted_repair": False,
    "final_source": {
        "title": "...",
        "content": "...",
        "path": "...",
        "episode_id": "ep_012",
    },
    "gate_reports": {
        "rules": {...},
        "structure": {...},
        "repair_rules": {...},
        "repair_structure": {...},
    },
    "errors": ["..."],
    "repair_summary": {
        "status": "not_needed" | "applied" | "failed",
        "reason": "",
    },
}
```

### Why `retry_possible` is not the final external status

The top-level design describes `publishable`, `retry_possible`, and `hard_fail`.

For v1, `retry_possible` will exist as an internal intermediate state inside the orchestrator, not as a long-lived runtime-visible status. The runtime should receive only:

- `publishable`
- `hard_fail`

This keeps `PublishingRuntime` simpler and avoids introducing a second persistent retry state before the system has a full quality repair history model.

## Gate Model

### Gate 1. Cheap rule validation

Reuse the current `publishing_quality.evaluate_publish_source(...)` as the first stage.

This stage should continue to catch inexpensive failures such as:

- missing or malformed title
- body too short
- blocked markers like draft or review-report leakage
- obviously invalid raw source

This stage is intentionally cheap and deterministic.

### Gate 2. Cheap structure validation

Add a dedicated structure validator for failures that are still cheap to detect but are more about publish-shape than raw presence checks.

For v1 this should stay narrow and deterministic. Candidate checks:

- heading exists and is usable
- apparent episode number in title and body heading does not conflict
- repeated line spam over threshold
- large leftover markers such as `초안`, `수정본`, `검수리포트`
- malformed body structure that looks like scaffolding instead of prose

This stage should not try to judge literary quality. It is still a cheap publish-shape gate.

## Repair Policy

### What qualifies as recoverable

`retry_possible` means:

- the failure is not fundamentally unsafe to publish
- the issue looks fixable by a short low-cost repair prompt
- the repair does not require generating a new chapter from scratch

Examples:

- heading normalization
- minor title cleanup
- obvious leftover draft markers
- boundary-length issues near threshold
- repeated helper lines that can be removed

### What is immediately `hard_fail`

Some failures should skip repair entirely:

- no usable title
- body effectively missing
- episode numbering clearly inconsistent
- obvious non-chapter artifact content
- structure still broken after one repair attempt

### One repair attempt only

For v1:

- maximum repair count is `1`
- no looped repair
- no fallback re-generation
- if repair output still fails any gate, final status becomes `hard_fail`

This is the right tradeoff for low cost and predictable automation behavior.

## Data Flow

The runtime flow becomes:

1. `PublishingRuntime.tick()` resolves the queue job and source payload.
2. It calls `QualityGateOrchestrator.evaluate(...)`.
3. The orchestrator runs:
   - cheap rules gate
   - cheap structure gate
   - optional one-shot repair
   - re-run of both gates on repaired output
4. The orchestrator returns a final normalized decision.
5. If `publishable`, runtime uses `final_source` for executor input.
6. If `hard_fail`, runtime does not call the executor and persists a blocked runtime state.
7. The orchestrator report is written to `runs/<run_id>/quality_report.json`.

This keeps the runtime coordinator-oriented while preserving traceability.

## Runtime Integration

### Current runtime behavior

Today `PublishingRuntime` does this:

1. load source
2. call `evaluate_publish_source(...)`
3. if not publishable, mark the job failed and stop
4. otherwise execute publish

### New runtime behavior

After this slice it should do this instead:

1. load source
2. call `QualityGateOrchestrator.evaluate(...)`
3. if final status is `hard_fail`:
   - mark job failed
   - set runtime to `blocked`
   - write gate report and error summary to history
   - do not call executor
4. if final status is `publishable`:
   - pass `final_source` downstream
   - continue through executor, incident summarization, and Canon finalize

The key change is that publish gating becomes a dedicated decision boundary, not just a single helper call.

## Planner Dependency Boundary

The top-level design expects planner-aware quality checks eventually. `_2` does not yet have the real `Episode Planner`, and the current `core/planner.py` is still idea-generation oriented.

For that reason, `Quality Gate Orchestrator v1` should not depend on a true planner output yet.

Instead, it may accept lightweight metadata only:

- `episode_id`
- `chapter_title`
- source path
- optional release policy context for thresholds

This keeps the boundary future-compatible without blocking the current slice on planner redesign.

## Reporting and Snapshots

For v1, `quality_report.json` should include:

- original source summary
- rules gate result
- structure gate result
- whether repair was attempted
- repaired source summary, if any
- final decision
- final error list

This report should be rich enough to explain:

- why a chapter was blocked
- whether repair was attempted
- whether the failure looked structural or irrecoverable

It should not store unnecessary full duplicate chapter bodies unless the current snapshot conventions already require that.

## Testing Strategy

### New unit tests

Add `tests/test_quality_gate_orchestrator.py` with at least:

- publishable when both cheap gates pass
- recoverable failure repaired once then passes
- recoverable failure repaired once then still fails -> `hard_fail`
- hard failure bypasses repair
- repair is attempted at most once

### Runtime integration tests

Extend `tests/test_publishing_runtime.py` to verify:

- orchestrator `hard_fail` blocks executor invocation
- runtime becomes `blocked` on orchestrator hard fail
- history and snapshot report include orchestrator output
- publishable repaired source can still flow into executor

### Regression target

This slice should preserve existing publish control plane behavior outside the quality boundary:

- release policy engine still decides whether a run is allowed
- executor filtering by allowed platforms still works
- incident summarization remains post-executor only
- Canon updates still happen only after successful publish

## Risks

### Risk 1. Repair prompt overreach

A repair step can accidentally rewrite more than intended.

Mitigation:

- keep repair prompt narrow
- use one attempt only
- restrict repair to structural cleanup, not story redesign

### Risk 2. False positives from structure checks

If structure checks are too rigid, valid chapters will be blocked.

Mitigation:

- keep v1 structure checks cheap and conservative
- prefer obvious artifact leakage and malformed-output detection over literary judgments

### Risk 3. Runtime state ambiguity

If all hard fails become `blocked`, some cases may later deserve `cooldown` or a different state.

Mitigation:

- accept `blocked` as the v1 runtime result for pre-executor quality failure
- refine state taxonomy later when critic gate and regeneration exist

## Non-goals

This slice intentionally does not implement:

- critic LLM gate
- full planner-aware narrative validation
- chapter re-generation
- multi-pass repair loops
- marketing packager
- locale pipeline
- long-term `stopped` state

## Recommendation

Implement `Quality Gate Orchestrator v1` as the next slice after `Release Policy Engine v1`.

This is the highest-value next step because it directly improves the two priorities that matter most for this project:

- quality stability
- cost control

It also matches the top-level design without prematurely expanding into critic models, marketing, or translation.
