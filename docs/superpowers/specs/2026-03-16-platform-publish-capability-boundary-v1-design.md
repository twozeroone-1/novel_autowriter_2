# Platform Publish Capability Boundary V1 Design

## Background

`_2` now has a meaningful distinction between:

- app-level scheduled work (`scheduled_at`)
- site-internal reserved publish (`publish_mode="reserved"`, `reserved_at`)

But the publishing UI still lets the operator choose `reserved` for any selected platform combination. That means the queue can be populated with an invalid intent such as:

- selected platforms: `munpia`, `novelpia`
- publish mode: `reserved`

At execution time this eventually fails because `MunpiaClient.set_publish_options(...)` explicitly rejects reserved scheduling, while `NovelpiaClient` accepts it.

That behavior is technically correct but too late. The control plane already knows the capability boundary:

- Munpia: immediate only
- Novelpia: immediate + reserved

So the queue editor should not let unsupported combinations through in the first place.

## Goal

Add a bounded capability surface so publish-mode support is declared once and used by the publishing UI before jobs enter the queue.

This slice should:

- declare per-platform publish-mode support near the platform client boundary
- expose a small helper for UI/policy consumers
- block invalid queue additions such as Munpia + reserved
- keep executor/runtime behavior unchanged as the last line of defense

## Approaches

### Option 1. Keep validation only in `set_publish_options(...)`

Pros:

- no extra code

Cons:

- invalid jobs still enter the queue
- user only discovers the limitation at execution time
- makes phase-3 control feel less deterministic

### Option 2. Add explicit platform capability metadata and validate in the queue UI

Pros:

- smallest change that moves the failure to the right boundary
- keeps runtime/executor protection intact
- gives other consumers a clean source of truth

Cons:

- adds one shared capability helper

### Option 3. Add a full platform feature registry and dynamic UI configuration system

Pros:

- strongest long-term abstraction

Cons:

- too large for the remaining phase-1~4 scope
- overkill when only publish-mode support is needed now

This spec chooses option 2.

## Scope

### In scope

- platform client publish-mode capability declaration
- shared helper for checking whether a platform supports a publish mode
- queue-editor validation for unsupported platform combinations
- focused tests in base/client/UI boundaries

### Out of scope

- Munpia reserved implementation
- platform capability storage in project config
- automatic UI reshaping per platform
- marketing or locale work

## Design

### 1. Capability declaration lives at the platform boundary

Publish-mode capability should be declared near the platform clients, not buried in UI conditionals.

Minimal model:

- `BasePlatformClient` exposes a class-level capability contract
- each concrete client overrides the supported modes it can actually handle

For this slice:

- `MunpiaClient.supported_publish_modes() -> ("immediate",)`
- `NovelpiaClient.supported_publish_modes() -> ("immediate", "reserved")`

This is intentionally narrow. It only answers the one question the control plane needs right now.

### 2. Shared helper for UI-safe capability checks

Add a small helper near the client boundary that:

- maps platform name to client class
- returns the supported publish modes for that platform
- answers whether a set of selected platforms all support a requested publish mode

The UI should not instantiate clients just to ask this question.

### 3. Queue editor validation

When the publishing tab queue form is submitted:

- if `publish_mode == "immediate"`, existing behavior continues
- if `publish_mode == "reserved"`, all selected platforms must support `reserved`

If any selected platform does not:

- the job is not added to the queue
- the UI shows a warning that names the unsupported platforms

This validation belongs right before queue persistence, so the form can stay mostly unchanged.

### 4. No runtime/executor behavior change

This slice should not relax the existing executor protections.

`MunpiaClient.set_publish_options(...)` should still reject reserved mode. That remains the last line of defense if invalid data arrives from older queues or external edits.

## Data Flow

1. User selects platforms and publish mode in the queue editor.
2. UI computes unsupported platforms for the chosen publish mode.
3. If unsupported platforms exist:
   - queue append is blocked
   - warning is shown
4. If all platforms support the mode:
   - existing queue payload is saved unchanged
5. Runtime/executor continue to enforce client-side rules as before.

## Testing

- `tests/test_platform_client_base.py`
  - publish-mode capability helper returns expected modes for Munpia and Novelpia
- `tests/test_munpia_client.py`
  - supported publish modes only include `immediate`
- `tests/test_novelpia_client.py`
  - supported publish modes include `reserved`
- `tests/test_publishing_ui.py`
  - helper reports unsupported platforms for reserved mode
  - reserved queue submissions are blocked when Munpia is selected
  - immediate mode remains allowed for mixed selections

## Non-goals

- making the publish-mode widget itself platform-aware
- capability-driven hiding of reserved fields
- future features such as draft visibility capability, age-grade capability, or scheduled reconciliation capability
