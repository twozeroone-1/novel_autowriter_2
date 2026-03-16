# Phases 1-4 Closeout Audit

## Purpose

This document audits the current `_2` implementation against phases 1-4 of the upstream design:

- [2026-03-14-fully-automated-web-novel-serialization-design.md](/mnt/c/Users/W/novel_autowriter_1/docs/superpowers/specs/2026-03-14-fully-automated-web-novel-serialization-design.md)

The goal is not to reopen broad design work. The goal is to decide whether phases 1-4 are operationally complete enough to stop adding speculative backend features and move on only when there is clear value.

Current evidence baseline:

- curated regression suite currently passes at `350 tests`
- publish control plane includes:
  - planner
  - quality gate
  - critic gate
  - regenerate-once
  - publish packager
  - platform adapters
  - release policy engine
  - scheduled reconciliation
  - UI/runtime visibility for scheduled work

## Audit Summary

### Decision

Treat phases 1-4 as **functionally closed for v1 Korean-origin automation**.

That means:

- the remaining gaps are no longer foundational blockers
- the largest unresolved item, `Munpia site-internal reserved publish`, should be treated as an optional platform-specific extension, not as a reason to keep broadening the core
- further work under phases 1-4 should be limited to bug fixes, smoke-test findings, or selector updates grounded in real platform evidence

### Status by phase

| Phase | Status | Notes |
| --- | --- | --- |
| 1. Story Bible / Canon DB / Run Snapshot | Closed | structured stores, artifact lifecycle, Canon gating, run snapshots are in place |
| 2. Episode Planner / Draft Writer / Quality Gate Orchestrator | Closed for v1 | planner, repair-once, critic gate, regenerate-once all exist; richer narrative heuristics remain optional |
| 3. Publish Packager / Munpia / Novelpia Adapter | Closed for v1 | packager, adapters, verification, Novelpia reserved + reconciliation are in place; Munpia reserved is intentionally unsupported |
| 4. Release Policy Engine / incident-driven state machine | Closed for v1 | policy engine, cooldown/blocked/stopped, platform windows, daily limits, burst gating, scheduled state are in place |

## Phase 1 Audit

### Implemented

- `Story Bible` is separated into structured storage.
- `Canon DB` is updated only after publish success and structured extraction success.
- `Context state` and `plot` are detached from generic config-first behavior.
- `Episode artifact` lifecycle is split across draft, publishable, and published.
- `Run snapshots` exist for quality reports, packager output, and Canon update data.

### Evidence

- `core/story_bible_store.py`
- `core/canon_store.py`
- `core/context_state_store.py`
- `core/plot_store.py`
- `core/episode_artifact_store.py`
- `core/run_snapshot_store.py`
- `core/context.py`

### Remaining gap assessment

No material blocker remains for phase 1. Any further work here is cleanup, not missing architecture.

## Phase 2 Audit

### Implemented

- `EpisodePlanner` produces a structured episode plan.
- `Generator` injects `[EPISODE PLAN]` into the draft prompt.
- `QualityGateOrchestrator` runs cheap rules, structure checks, one-shot repair, critic gate, and regenerate-once.
- `CanonExtractor` exists and is wired into publish-time Canon finalize.

### Evidence

- `core/episode_planner.py`
- `core/generator.py`
- `core/quality_gate_orchestrator.py`
- `core/publishing_quality.py`
- `core/publishing_structure.py`
- `core/publishing_repair.py`
- `core/publishing_critic.py`
- `core/publishing_regenerate.py`
- `core/canon_extractor.py`

### Remaining gap assessment

The remaining items are quality improvements, not missing v1 structure:

- stronger planner-aware narrative heuristics
- critic-guided auto-repair instead of binary block
- multi-pass regenerate loops

These should stay out of the critical path unless smoke tests show a real failure mode.

## Phase 3 Audit

### Implemented

- `PublishPackager` exists as its own boundary.
- `PublishingExecutor` no longer hand-builds payloads inline.
- adapters implement:
  - `login`
  - `ensure_work`
  - `upload_episode`
  - `set_publish_options`
  - `verify_publication`
- `Novelpia reserved publish` exists.
- `scheduled reconciliation` exists and resolves scheduled jobs later.
- UI and history now surface scheduled state explicitly.

### Evidence

- `core/publish_packager.py`
- `core/publishing_executor.py`
- `core/platform_clients/base.py`
- `core/platform_clients/munpia.py`
- `core/platform_clients/novelpia.py`
- `core/publishing_runtime.py`
- `ui/publishing.py`

### Remaining gap assessment

The only major visible omission is `Munpia site-internal reserved publish`.

This should **not** block phase-3 closeout for three reasons:

1. There is no strong selector evidence for a reliable Munpia reserved flow in the current codebase or the older `_1` codebase.
2. The capability boundary now explicitly marks Munpia as `immediate` only, so unsupported intent is blocked before queue persistence.
3. The upstream spec requires platform adapters and publish-option handling, not that every platform support identical scheduling features.

Conclusion: phase 3 is closed for v1 as long as Munpia reserved remains an explicit non-goal instead of a silent gap.

## Phase 4 Audit

### Implemented

- `ReleasePolicyEngine` exists as a separate policy boundary.
- policy supports:
  - enabled/paused/stopped handling
  - platform daily limits
  - burst/second-slot rules
  - cooldown after retryable failures
  - platform-specific time windows
- incident handling distinguishes:
  - quality incidents
  - platform incidents
  - requires-user-action paths
  - scheduled waiting state
- runtime and UI both surface:
  - `scheduled`
  - `cooldown`
  - `blocked`
  - `stopped`
  - `paused`

### Evidence

- `core/release_policy_engine.py`
- `core/release_policy_store.py`
- `core/publishing_policy.py`
- `core/publishing_incidents.py`
- `core/publishing_runtime.py`
- `ui/publishing.py`

### Remaining gap assessment

There is no compelling foundational blocker left in phase 4.

Possible future refinements:

- explicit `needs_human` state name, separate from `paused`
- project-wide daily cap in addition to platform-level caps
- richer scheduled-state dashboards

These are useful refinements, but not reasons to keep phase 4 open.

## What Is Explicitly Deferred

The following should be treated as deferred, not as hidden incompleteness:

- `Munpia site-internal reserved publish`
- richer narrative critic heuristics beyond current gates
- additional publication re-fetch sophistication beyond current verification paths
- phase 5 `Marketing Packager`
- phase 6 `Translation Boundary / locale pipeline`

## Recommended Next Move

Do **not** keep expanding phases 1-4 by default.

Recommended next actions, in order:

1. run manual smoke tests against real platform test accounts
2. treat any smoke-test failures as selector/adapter bugfix work under phases 3-4
3. if smoke tests hold, decide whether to start phase 5 or pause and stabilize

## Final Judgment

For the purpose of this repository and current evidence, phases 1-4 should now be considered:

**closed for v1 implementation scope**

That does not mean "perfect" or "never change again". It means the remaining work is no longer missing core architecture. It is either:

- validation against real platforms
- explicit deferred platform-specific enhancement
- or phase-5/6 scope
