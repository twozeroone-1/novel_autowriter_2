# Operations Overview Screen V2 Design

## Purpose

The first `운영 개요` slice established a status-first screen, but it still stops short of the original wireframe intent:

- it summarizes readiness
- it lists blockers
- it lists next actions

What it still does not do well:

- show where the current episode is in the end-to-end pipeline
- show operator shortcuts in a structured way

This slice closes that gap by adding:

- an episode-state timeline
- explicit shortcut actions grouped by likely destination

## Scope

In scope:

- strengthen `ui/operations_dashboard.py`
- surface a compact timeline for `설정 -> 계획 -> 생성 -> 품질 -> 발행 -> 후속 검증`
- surface structured shortcut actions
- keep the current `운영 개요` layout and metrics

Out of scope:

- programmatic tab switching
- removing legacy tabs
- changing backend publishing logic

## Problems To Solve

### 1. The dashboard still reads like a summary, not a control surface

The current screen tells the operator what is wrong, but it does not make the current stage visually obvious.

### 2. The wireframe promised a timeline and action shortcuts

The wireframe spec explicitly called for:

- an episode-state timeline
- action shortcuts

The current implementation has neither.

### 3. Operators still need to infer which tab to open next

The existing `다음 권장 작업` is free-form text. That is useful, but weak as a navigation aid.

## Approach

### Option 1. Add only more recommendation text

Pros:

- tiny change

Cons:

- still weakly visual
- does not satisfy the wireframe intent

### Option 2. Add a timeline row and structured shortcut list

Pros:

- best balance
- keeps current dashboard stable
- makes current stage and next destination obvious

Cons:

- some duplication with workflow/publishing tabs remains

### Option 3. Turn the dashboard into a button-heavy launcher

Pros:

- strong operator feel

Cons:

- Streamlit tab switching is awkward
- too much interaction complexity for this slice

This design chooses option 2.

## Target UI

Keep the existing summary metrics and readiness/blocker sections.

Add two new sections below `다음 권장 작업`:

### 1. 오늘의 회차 상태 타임라인

Render six compact stages:

- 설정
- 계획
- 생성
- 품질
- 발행
- 후속 검증

Each stage should show one of:

- `완료`
- `현재`
- `차단`
- `다음`

### 2. 바로가기 액션

Render a small structured list such as:

- `프로젝트 통합 설정 열기`
- `회차 워크플로 보기`
- `발행 운영 확인`
- `자동화/진단 확인`

These are guidance labels, not tab-switching buttons.

## Data Model

`build_operations_overview_snapshot(...)` should additionally return:

- `timeline_steps`
- `shortcut_actions`

To compute timeline state, the dashboard should consider:

- required workspace fields
- latest episode plan presence
- latest stored episode artifact presence
- latest quality report status
- latest publish queue/runtime state

This does not need perfect state modeling. It only needs a stable operational approximation of the current episode phase.

## Testing

Update `tests/test_operations_dashboard.py` to cover:

- timeline reflects a healthy flow with completed settings and a publishable quality result
- blocked runtime or hard-fail quality marks the right stage as blocked
- shortcut actions include the expected destination labels

## Expected Outcome

After this slice, the first screen should do three jobs well:

- summarize readiness
- explain blockers
- show both current phase and where to go next

That moves `운영 개요` much closer to the original operations-console intent without introducing disruptive navigation changes.
