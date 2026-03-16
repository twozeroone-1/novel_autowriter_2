# Episode Workflow Screen V2 Design

## Purpose

The current `회차 워크플로` screen already shows the four pipeline stages, but it still under-exposes the state that actually matters when operating the pipeline:

- what the latest draft looks like
- whether critic blocked or passed
- whether repair/regenerate happened
- whether the packaged episode is already linked to a pending publish job

This slice strengthens the workflow screen without deleting legacy tabs. The goal is to make the workflow tab useful enough that operators only drop into `회차 생성`, `원고 검수`, or `발행 운영` when they need to act.

## Scope

In scope:

- strengthen `ui/episode_workflow.py`
- surface latest draft preview and file status
- surface critic/repair/regenerate details in the workflow summary
- surface publishing queue linkage for the latest episode
- add explicit next-step shortcuts as guidance text

Out of scope:

- removing legacy tabs
- adding programmatic tab switching
- redesigning the generator/reviewer/publishing pipelines

## Problems To Solve

### 1. Draft stage is too abstract

The current draft step only shows `title / status`. Operators still need to guess whether the latest stored draft is meaningful.

### 2. Quality stage hides the most important details

The current quality summary compresses useful information into one line. It does not clearly separate:

- critic result
- repair applied
- regenerate applied
- hard-fail reason

### 3. Packager stage does not show queue linkage

The current packager summary says packages exist, but it does not show whether the latest episode is already tied to a pending publish job.

### 4. Workflow guidance is text-only and generic

The screen has next actions, but the guidance still behaves like a summary panel rather than a workflow control surface.

## Approach

### Option 1. Only add more summary lines

Pros:

- minimal code churn

Cons:

- still weakly structured
- does not make the four-step workflow more legible

### Option 2. Add stage-specific status cards inside the workflow screen

Pros:

- best balance
- keeps current screen structure
- makes each stage operationally meaningful

Cons:

- some information duplication with other tabs remains

### Option 3. Replace legacy tabs with the workflow screen

Pros:

- strongest workflow framing

Cons:

- too disruptive for this slice
- requires more navigation work than the current request needs

This design chooses option 2.

## Target UI

The screen remains:

- top row: four stage states
- left column: current stage summary + next actions
- right column: stage detail

But the detail and summary content becomes richer.

### Draft detail

Show:

- latest episode id, title, status
- artifact path if available
- short excerpt preview from the markdown body

### Quality detail

Show:

- overall status
- critic status
- repair applied yes/no
- regenerate applied yes/no
- top error summary if blocked

### Packager detail

Show:

- prepared platforms
- whether a pending/scheduled queue job already references the latest episode
- queue-linked title/platform summary

### Guidance shortcuts

Add explicit operator guidance text:

- `회차 생성 탭으로 이동해 새 초안을 만드세요`
- `원고 검수에서 차단 사유를 먼저 해결하세요`
- `발행 운영에서 큐와 플랫폼 상태를 확인하세요`

These remain text guidance for now. They do not attempt tab switching.

## Data Additions

`build_episode_workflow_snapshot(...)` should additionally return:

- `draft_preview`
- `draft_path`
- `critic_status`
- `repair_applied`
- `regenerate_applied`
- `queue_linked`
- `queue_link_summary`

The latest draft preview should be read from the latest episode artifact path on disk, not inferred from stored summaries.

Queue linkage should be inferred by matching the latest episode title against pending/scheduled publish queue jobs.

## Testing

Add or update tests in `tests/test_episode_workflow.py` to cover:

- latest episode draft excerpt is surfaced from stored markdown
- publishable quality summary exposes critic/repair/regenerate flags
- pending queue tied to the latest episode is surfaced in packager detail
- hard-fail quality still recommends fixing quality before publish

## Expected Outcome

After this slice, `회차 워크플로` should act as the operational center for one episode:

- plan visible
- draft visible
- quality decision visible
- publish readiness visible

The legacy tabs remain available for editing and execution, but the workflow screen becomes the primary place to understand what is happening.
