# Operations Dashboard UI Wireframe Design

## Purpose

Phases 1-4 are now functionally closed for v1 Korean-origin automation. The next problem is not missing backend capability. The problem is that the UI still feels like a tool box of tabs instead of an operations console.

This spec defines the next UI direction at wireframe level:

- keep the existing Streamlit app structure
- keep current feature coverage
- shift the product from "many editing panels" toward "status-first operations dashboard"

The goal is not a visual redesign first. The goal is to make the system legible:

- Is this project publishable right now?
- What is blocking the next episode?
- Which platform is ready, broken, paused, or scheduled?
- What should the operator do next?

## Current UI Problems

### 1. Status is buried under tabs

The current app opens on project settings and exposes capability by tab number:

- `[1] 프로젝트 통합 설정`
- `[2] 회차 생성`
- `[3] 원고 검수`
- `[4] 반자동 연재 모드`
- `[5] 자동화 연재 모드`
- `[6] 외부 플랫폼 업로드`

This is clear for development, but weak for operations. It answers "what can I click?" better than "what is the current state?"

### 2. Publishing UI is configuration-heavy, status-light

`ui/publishing.py` already contains meaningful runtime and queue state, but the top of the screen still behaves like a settings form:

- platform forms
- schedule form
- queue form
- runtime/history

An operator really needs the inverse order:

- readiness summary
- current blocker
- pending/scheduled work
- then settings

### 3. Story/planning state is disconnected from publishing state

The system now has:

- structured Story Bible
- Episode Planner
- Quality Gate Orchestrator
- Critic gate
- Publish Packager
- Release Policy Engine

But the UI still presents these as scattered panels rather than one episode workflow.

## Design Goal

Reshape the app into three layers:

1. `작품 운영 개요`
2. `이번 회차 워크플로`
3. `플랫폼 운영/설정`

This can still live inside the current Streamlit shell, but the information hierarchy should invert:

- status first
- actions second
- raw settings third

## Approaches

### Option 1. Keep the tab layout and only polish labels

Pros:

- minimal code churn

Cons:

- does not solve the "tool box" problem
- still hides blockers and readiness state

### Option 2. Add an operations dashboard as the first screen, keep existing tabs behind it

Pros:

- safest migration
- reuses existing implementation
- gives operators one summary surface without deleting current workflows

Cons:

- some duplication remains between dashboard cards and tab content

### Option 3. Fully replace tabs with a step-based wizard

Pros:

- strongest workflow framing

Cons:

- too disruptive for current users
- higher implementation cost

This spec chooses option 2.

## Target Information Architecture

### Top navigation

Replace the current numbered tab emphasis with:

- `운영 개요`
- `작품 설정`
- `회차 워크플로`
- `발행 운영`
- `자동화/진단`

The existing internal modules can remain, but the presented navigation should reflect user intent rather than implementation order.

## Screen 1: Operations Overview

### Purpose

Give a one-screen answer to:

- what is healthy
- what is blocked
- what is next

### Wireframe

```text
+--------------------------------------------------------------+
| 작품명 | 현재 단계 | 오늘 일정 | 마지막 실행 시각            |
+--------------------------------------------------------------+
| 상태 카드 1 | 상태 카드 2 | 상태 카드 3 | 상태 카드 4      |
| 설정 준비   | 이번 화 계획 | 품질 게이트   | 플랫폼 준비도    |
+--------------------------------------------------------------+
| 주요 경고 / 차단 사유                                      |
| - 문피아 work_id 없음                                      |
| - 노벨피아 smoke 미실행                                    |
+--------------------------------------------------------------+
| 다음 권장 작업                                             |
| [플랫폼 smoke 실행] [이번 화 계획 보기] [업로드 큐 열기]   |
+--------------------------------------------------------------+
| 오늘의 회차 상태 타임라인                                  |
| 설정 -> 계획 -> 생성 -> 검수 -> 발행 -> 후속 검증         |
+--------------------------------------------------------------+
```

### Components

- `작품 상태 헤더`
  - current project name
  - current runtime state
  - next release window
- `상태 카드`
  - `설정 준비도`
  - `이번 화 준비도`
  - `발행 준비도`
  - `플랫폼 연결 상태`
- `차단 사유 패널`
  - only visible when something is blocked, paused, stopped, or missing
- `다음 행동 버튼`
  - context-sensitive shortcuts into existing tabs/forms

## Screen 2: Episode Workflow

### Purpose

Make episode production legible as one continuous pipeline.

### Wireframe

```text
+--------------------------------------------------------------+
| 이번 화 워크플로                                            |
+--------------------------------------------------------------+
| [1 계획] [2 초안] [3 품질 게이트] [4 발행 패키지]          |
+--------------------------------------------------------------+
| 왼쪽: 현재 단계 요약                                        |
| - 회차 목표                                                 |
| - 등장인물                                                  |
| - 금지사항                                                  |
| - 분량 목표                                                 |
|                                                              |
| 오른쪽: 단계 상세                                            |
| - episode_plan.json 미리보기                                |
| - 생성 결과 요약                                             |
| - critic 판정                                                |
| - regenerate/repair 여부                                     |
+--------------------------------------------------------------+
```

### Notes

- This is not a new generator. It is a new surface over:
  - `episode_planner`
  - `generator`
  - `quality_gate_orchestrator`
  - `publish_packager`
- Each step should show:
  - `ready`
  - `warning`
  - `blocked`
  - `done`

## Screen 3: Publishing Operations

### Purpose

Turn the current publishing tab into an operator console.

### Wireframe

```text
+--------------------------------------------------------------+
| 플랫폼 운영                                                  |
+--------------------------------------------------------------+
| 문피아 카드              | 노벨피아 카드                    |
| 상태: 미연결             | 상태: 예약 대기                  |
| 계정: 없음/있음          | 계정: 연결됨                     |
| work_id: 없음/있음       | work_id: 416704                  |
| smoke: 미실행/성공/실패  | smoke: 성공                      |
| [이 플랫폼 smoke]        | [이 플랫폼 smoke]                |
+--------------------------------------------------------------+
| 업로드 큐                                                   |
| 회차 | 대상 | 발행 방식 | 시작 시각 | 상태                 |
+--------------------------------------------------------------+
| 실행 상태 / 최근 이력                                       |
| runtime state | last error | scheduled follow-up           |
+--------------------------------------------------------------+
| 고급 설정 접기                                              |
| - selector override                                         |
| - create/upload URL                                         |
| - default visibility                                        |
+--------------------------------------------------------------+
```

### Change from current UI

Move from:

- settings first
- queue second
- history last

To:

- platform readiness first
- queue and scheduled jobs second
- settings in collapsed advanced sections

## Screen 4: Project Settings

### Purpose

Keep Story Bible and long-form settings available, but reduce their dominance on app entry.

### Wireframe

```text
+--------------------------------------------------------------+
| 작품 설정                                                    |
+--------------------------------------------------------------+
| 문서 상태 요약                                               |
| STORY_BIBLE | STYLE_GUIDE | CONTINUITY | STATE             |
+--------------------------------------------------------------+
| 본문 편집 패널                                               |
| - selected document editor                                  |
| - AI assist actions                                          |
| - PREVIOUS SUMMARY                                           |
+--------------------------------------------------------------+
| 구조화 저장소 현황                                           |
| canon summary | release policy summary                      |
+--------------------------------------------------------------+
```

### Change from current UI

- preserve existing editors
- move them behind a clearer document-status summary
- stop using this screen as the app's implicit "home"

## Screen 5: Automation / Diagnostics

### Purpose

Keep advanced runtime controls accessible without cluttering daily operations.

### Wireframe

```text
+--------------------------------------------------------------+
| 자동화 / 진단                                                |
+--------------------------------------------------------------+
| 자동화 상태                                                  |
| - 반자동                                                     |
| - 자동화                                                     |
| - 발행 런타임                                                |
+--------------------------------------------------------------+
| 실행 기록                                                    |
| - LLM runs                                                   |
| - automation history                                         |
| - publishing history                                         |
+--------------------------------------------------------------+
| 디버그 패널                                                  |
| - latest quality report                                      |
| - latest packager report                                     |
| - latest canon update                                        |
+--------------------------------------------------------------+
```

## Shared Status Language

Unify the same vocabulary across all screens:

- `준비됨`
- `주의 필요`
- `차단됨`
- `일시중지`
- `예약 대기`
- `실행 중`
- `완료`

The same runtime state should not appear as different labels in different screens unless the difference is intentional.

## Mapping from Current Modules

### Reused as-is or almost as-is

- `ui/publishing.py`
  - runtime/history helpers
  - queue helpers
  - platform settings forms
- `ui/workspace.py`
  - field panels
  - structured-store summaries
- `ui/chapters.py`
  - generation and review surfaces
- `ui/automation.py`
  - automation status helpers
- `ui/diagnostics.py`
  - run history and detail rendering

### New UI boundaries recommended

- `ui/operations_dashboard.py`
  - top-level overview screen
- `ui/workflow_dashboard.py`
  - episode production pipeline surface
- `ui/publishing_dashboard.py`
  - status-first publishing cards over existing publishing helpers

This keeps implementation incremental instead of forcing a full rewrite.

## Migration Strategy

### Phase A

- Add `운영 개요` as a new first screen
- Keep all current tabs available underneath

### Phase B

- Reorder publishing tab to show readiness cards first
- Collapse raw platform settings by default

### Phase C

- Add workflow dashboard using existing planner/quality artifacts

This sequence gives visible UX value without blocking on a large refactor.

## Implementation Priority

If this UI work starts immediately after phase-1~4 closeout, priority should be:

1. `운영 개요` top screen
2. publishing readiness cards and smoke entry points
3. episode workflow dashboard
4. project settings reframe

## Final Recommendation

Do not redesign the app cosmetically first.

Build a status-first operations dashboard that sits on top of the existing tabs and helpers. The current system already has the backend signals needed for a stronger UI. The right next move is to surface them clearly, not to invent new backend behavior first.
