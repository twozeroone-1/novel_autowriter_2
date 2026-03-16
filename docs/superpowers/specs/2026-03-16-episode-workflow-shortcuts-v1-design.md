# Episode Workflow Shortcuts V1 Design

## Purpose

The UI now has a real `회차 워크플로` center screen, but the surrounding navigation still gives equal visual weight to legacy task-specific tabs:

- `회차 생성`
- `원고 검수`
- `반자동 연재 모드`

This slice rebalances the UI without removing those tools:

- make legacy task tabs visibly secondary
- make the workflow screen explicitly point to them when the operator needs to act

## Scope

In scope:

- rename tab labels so legacy episode-production tabs read as advanced tools
- add structured shortcut actions to `회차 워크플로`
- keep existing tabs and implementations intact

Out of scope:

- removing tabs
- programmatic tab switching
- changing generator/reviewer behavior

## Approach

Use the existing eight-tab shell, but change the information hierarchy.

### Navigation change

Keep:

- `운영 개요`
- `회차 워크플로`
- `작품 설정`
- `자동화/진단`
- `발행 운영`

Demote legacy task tabs by renaming them:

- `고급: 회차 생성`
- `고급: 원고 검수`
- `고급: 반자동 실행`

### Workflow shortcut actions

Add structured actions to the workflow snapshot, separate from free-form `다음 권장 작업`.

Examples:

- `작품 설정 열기`
- `고급: 회차 생성 열기`
- `고급: 원고 검수 열기`
- `발행 운영 열기`

The action list should be context-sensitive:

- no latest episode -> generation shortcut first
- hard-fail quality -> review shortcut first
- publishable but not packaged -> publishing shortcut first

## Testing

Update:

- `tests/test_ui_helpers.py` for tab labels
- `tests/test_episode_workflow.py` for structured shortcut actions

## Expected Outcome

After this slice:

- the app reads more clearly as `overview -> workflow -> operations`
- the old production tabs remain available, but no longer compete as primary navigation
- the workflow screen makes the next destination obvious
