# Release Policy Engine v1 Design

## Background

`_2` already has the storage layer for release policy and the first cut of the publish control plane.

- `core/release_policy_store.py` persists policy defaults and per-platform overrides.
- `core/publishing_policy.py` selects a runnable job based on a simple schedule check.
- `core/publishing_runtime.py` coordinates quality, executor, incident summarization, and Canon finalize.

What is still missing is the actual `Release Policy Engine` described in the higher-level system design. Right now the runtime can answer only a narrow question: "is the schedule due right now?" It cannot answer the more important question: "is this platform allowed to publish right now under the current policy, runtime state, and recent history?"

That gap matters because the v1 system requirements already depend on policy-aware behavior:

- platform-specific daily release caps
- optional same-day two-release bursts
- retry cooldown after retryable platform failures
- blocking behavior for quality hard fails and data integrity incidents
- preserving `paused` as a user-action-required state

Without that boundary, `PublishingRuntime` will keep absorbing policy logic and become the same kind of oversized runtime file that the new architecture is supposed to prevent.

## Goal

Add a minimal but real `Release Policy Engine v1` that decides whether publishing is allowed right now, for which platforms, and under which slot conditions, without yet introducing a separate ledger store or global project-wide daily cap.

This stage should satisfy the next concrete slice of the top-level design while keeping scope deliberately tight:

- support per-platform daily release limits
- support optional same-day second release only after a first real success
- support `cooldown`, `paused`, and `blocked` policy behavior
- keep current executor and publishing history structures usable

## Why This Slice

The higher-level implementation order says the next major milestone after the current publishing integration is:

1. Story Bible / Canon DB / Run Snapshot
2. Episode Planner / Draft Writer / Quality Gate
3. Publish Packager / platform adapter integration
4. Release Policy Engine and incident-driven runtime state machine

`_2` is already partway through step 4, but only at the incident/runtime side. This spec closes the policy half of that milestone.

## Approaches

### Option 1. Keep extending `publishing_policy.py`

Add daily caps, burst rules, and cooldown checks directly into the current runnable-job selector.

Pros:

- fastest implementation
- minimal file churn

Cons:

- mixes policy evaluation with job selection
- pushes more logic back into the same thin boundary we just created
- makes future expansion to global limits and richer policy rules harder

### Option 2. Add a dedicated `release_policy_engine.py`

Create a separate engine that evaluates policy first, then lets `publishing_policy.py` decide which queued job to run inside the policy-approved window.

Pros:

- matches the top-level system design
- keeps policy reasoning separate from queue selection
- makes future extension to project-wide limits, stop rules, and richer slot logic straightforward

Cons:

- slightly more implementation effort now

### Option 3. Introduce a dedicated policy ledger store immediately

Track daily release counters and burst-slot consumption in a new persistent ledger rather than deriving them from history.

Pros:

- strongest long-term data model
- avoids repeated history scans

Cons:

- too much for v1 of this slice
- duplicates information already derivable from existing publish history
- raises migration and correctness questions before they are necessary

This spec chooses option 2.

## Scope

### In scope

- new `ReleasePolicyEngine` module
- policy-aware decision object returned before job selection
- per-platform daily release cap
- per-platform same-day second release gating
- cooldown gating for retryable platform failures
- blocked gating for quality hard fail and data integrity incidents
- runtime integration with current publishing flow
- tests for engine behavior and runtime orchestration

### Out of scope

- project-wide daily total release cap
- third release slot or arbitrary burst windows
- separate ledger store
- marketing generation
- locale or translation pipeline
- full `stopped` long-term halt policy
- platform client redesign

## Proposed Architecture

### New module: `core/release_policy_engine.py`

This module owns the answer to:

`Given current policy, runtime, history, queue, and now, is publishing allowed right now?`

It does not choose the job body or run quality gates. It only returns a normalized policy decision.

### Existing module split after this change

- `core/release_policy_store.py`
  - persists policy configuration only
- `core/release_policy_engine.py`
  - evaluates whether publishing is allowed right now
- `core/publishing_policy.py`
  - selects the first runnable queued job after policy says a run is allowed
- `core/publishing_runtime.py`
  - orchestrates `policy engine -> job selection -> quality -> executor -> incidents -> canon`

This keeps the policy layer independent from queue semantics.

## Policy Model

### Input sources

The engine will read:

- release policy payload from `ReleasePolicyStore`
- current runtime state from `PublishingStore.load_runtime()`
- recent publishing history from `PublishingStore.load_recent_history(...)`
- current queue from `PublishingStore.load_queue()`
- current timestamp passed into `tick()`

### Policy defaults already available

The current store already exposes a shape like:

```json
{
  "global": {
    "max_daily_releases": 1,
    "burst_allowed": false,
    "cooldown_failures": 2
  },
  "platforms": {
    "munpia": {
      "enabled": false,
      "default_times": ["21:00"],
      "max_daily_releases": 1
    },
    "novelpia": {
      "enabled": false,
      "default_times": ["21:00"],
      "max_daily_releases": 1
    }
  }
}
```

`Release Policy Engine v1` will consume this shape as-is instead of redesigning it.

## Decision Contract

The engine should return a normalized structure like:

```python
{
    "action": "run_now" | "skip",
    "reason": "",
    "allowed_platforms": ["munpia"],
    "blocked_platforms": {
        "novelpia": "daily_limit_reached",
    },
    "burst_slot": False,
    "next_runtime_status": "idle",
}
```

### Meaning of the fields

- `action`
  - whether publishing is policy-allowed right now at all
- `reason`
  - top-level skip reason such as `paused`, `cooldown`, `blocked`, `not_due`, `no_platform_slot`
- `allowed_platforms`
  - platforms that still have a valid slot at this moment
- `blocked_platforms`
  - per-platform denial reasons
- `burst_slot`
  - whether the current allowance represents the second same-day burst slot
- `next_runtime_status`
  - policy-side runtime state if the engine must gate execution now

This contract is intentionally smaller than a full long-term policy engine. It is enough for v1 behavior while leaving room to grow.

## Policy Rules

### 1. Platform enablement

If a platform is disabled in release policy or publishing config, it gets no slot.

This is policy-level filtering, not executor-level failure.

### 2. Daily limit is per platform

Each platform uses its own `max_daily_releases`.

For v1:

- `munpia` and `novelpia` are counted independently
- there is no project-wide total cap yet

### 3. Burst means "second same-day release after first real success"

`burst_allowed` never means "always allow two."

It means:

- the platform may open a second slot on the same day
- only if a first successful publish already happened on that same platform and same day

If that first success does not exist yet, the second slot remains locked.

### 4. Cooldown applies only to retryable platform failure

`cooldown` should be entered only when the most recent relevant publishing outcome is retryable at the platform layer.

Examples:

- upload timeout
- transient editor failure
- navigation failure that should be retried later

It should not be used for:

- quality hard fail
- missing targets
- malformed job data
- explicit user-action-required states

### 5. Blocked is for non-retryable policy stop states

The engine should treat these as `blocked`:

- quality hard fail
- `data_integrity_incident`
- missing selected target situation
- policy state that should not auto-retry

Blocked means the engine does not reopen a slot automatically.

### 6. Paused remains user-action-required

If runtime is already `paused`, the engine returns skip immediately.

This preserves the current meaning:

- credentials missing
- captcha
- manual intervention required

### 7. Force run stays narrower than policy run

`force=True` should still bypass schedule timing, but it should not ignore `paused` or `blocked` states. The operator can force a schedule bypass, not silently bypass policy safety.

## Data Flow

After this change, the runtime flow becomes:

1. `PublishingRuntime.tick()` loads config, runtime, queue, history, release policy.
2. `ReleasePolicyEngine.evaluate(...)` decides whether any platform slot is open right now.
3. If the engine returns `skip`, runtime exits without selecting a job.
4. If the engine returns `run_now`, `publishing_policy.select_runnable_job(...)` chooses the first pending or partial-failed job.
5. Runtime filters that job's selected targets down to the policy-approved platform set for this slot.
6. Quality gate runs.
7. Executor runs.
8. Incident summarizer updates runtime/job status.
9. History written in this tick becomes future policy input.
10. Canon finalize continues to run only after successful publish outcome.

The critical change is that schedule due no longer directly implies execution. Policy approval sits in front of queue selection.

## Interaction with Current Files

### `core/release_policy_store.py`

No large redesign in this step. The store remains persistence-only.

Possible small changes:

- add a helper for normalized platform policy lookup
- extend defaults only if the engine needs one extra field and that field is truly necessary

### `core/publishing_runtime.py`

Will gain:

- release policy store load
- engine evaluation call before job selection
- target filtering based on `allowed_platforms`

Will not gain:

- inline daily-count logic
- inline burst-slot logic
- inline cooldown window math

### `core/publishing_policy.py`

This module remains a queue selector.

It should not decide:

- whether a platform has already hit its daily cap
- whether burst slot is unlocked
- whether cooldown or blocked state should suppress execution

That belongs to the engine.

## History-Derived Counting

V1 intentionally derives daily counts from existing publish history instead of adding a ledger.

The engine should count only real successful platform outcomes for the current day.

For example:

- history record success false -> does not count toward release cap
- history record success true but platform result failed for that platform -> does not count for that platform
- successful platform publish on current day -> counts toward that platform's daily usage

This keeps the system cheap and avoids premature storage complexity.

## Testing Strategy

### New test file

Add `tests/test_release_policy_engine.py`.

Minimum cases:

- daily cap of 1 prevents a second same-day platform publish
- `burst_allowed=True` does not unlock slot 2 before first same-day success
- first same-day success unlocks slot 2 when burst is enabled
- retryable platform failure yields `cooldown`
- quality hard fail yields `blocked`
- data integrity incident yields `blocked`
- paused runtime yields immediate skip

### Runtime regression updates

Update `tests/test_publishing_runtime.py` only enough to assert:

- runtime exits when engine returns `skip`
- runtime uses `allowed_platforms` before executor call
- runtime preserves current incident and canon flow after policy approval

The runtime tests should stay coordinator-focused.

## Non-goals

This design does not include:

- project-wide daily release cap
- policy-aware marketing generation
- translation-aware scheduling
- third release slot
- full long-term stop state machine
- platform-specific rest windows more complex than cooldown

## Completion Criteria

This spec is complete when:

1. A dedicated `release_policy_engine.py` exists.
2. Publishing runtime evaluates policy before choosing a job.
3. Policy can deny execution based on:
   - per-platform daily cap
   - locked second burst slot
   - cooldown
   - blocked
   - paused
4. Same-day second release is allowed only after first same-day success when burst is enabled.
5. Tests cover the engine directly and preserve runtime coordination regressions.
6. No new policy ledger store is introduced in this slice.
