# Project Settings Status-First V1 Design

## Purpose

`[1] 프로젝트 통합 설정`은 현재 기능은 많지만 정보 우선순위가 약하다. 화면을 열면 긴 편집 폼이 먼저 보이고, 사용자는 어떤 문서가 비었는지, 무엇이 생성 품질에 가장 큰 영향을 주는지, 다음에 무엇을 해야 하는지를 바로 알기 어렵다.

이번 slice의 목표는 기존 편집 기능을 유지한 채, 이 화면을 `상태 우선 허브`로 재구성하는 것이다.

- 기존 Story Bible / Style Guide / Continuity / State 편집 기능 유지
- `PREVIOUS SUMMARY`를 같은 탭 안에 유지
- 구조화 저장소 개요, 등장인물 관리, 진단 상세도 유지
- 화면 상단을 `현재 준비 상태`, `주의 문서`, `다음 작업` 중심으로 재배치

## Problem

현재 화면은 다음 문제가 있다.

1. 상태보다 편집기가 먼저 나온다.
2. 핵심 네 문서 중 무엇이 비었는지, 과한지, 괜찮은지 한눈에 보이지 않는다.
3. `PREVIOUS SUMMARY`가 별도 expander 아래에 있지만, 현재 요약이 실질적으로 필요한 상태인지 즉시 드러나지 않는다.
4. 구조화 저장소와 캐릭터/진단 도구가 모두 하단에 몰려 있어 운영 맥락이 약하다.

결과적으로 이 탭은 `설정을 바꾸는 곳`으로는 기능하지만, `작품 기준선을 점검하는 곳`으로는 약하다.

## Approaches

### Option 1. 현재 편집기 위에 메트릭만 추가

장점:

- 구현이 가장 작다.

단점:

- 여전히 긴 편집 폼이 먼저 보인다.
- 상태 우선 정보 구조로 바뀌지 않는다.

### Option 2. 상태 우선 허브 + 기존 편집기 하향 배치

장점:

- 현재 기능을 유지하면서 정보 우선순위를 바꿀 수 있다.
- 기존 helper와 저장 경계를 거의 그대로 재사용할 수 있다.
- operations dashboard wireframe 방향과 맞는다.

단점:

- 화면 길이는 여전히 길다.
- summary 정보와 편집기 정보가 일부 중복된다.

### Option 3. 설정 탭을 여러 하위 화면으로 완전 분해

장점:

- 장기적으로는 가장 깔끔하다.

단점:

- 이번 slice 범위가 커진다.
- 기존 사용 흐름을 많이 흔든다.

이번 slice는 Option 2를 선택한다.

## Target Design

### 1. 상단 상태 요약

헤더 아래에 먼저 다음을 보여준다.

- `핵심 문서 준비도`
  - Story Bible / Style Guide / Continuity / State 중 몇 개가 채워졌는지
- `확인 필요 문서`
  - 비어 있거나 길이 조정이 필요한 문서 수
- `PREVIOUS SUMMARY`
  - 비어 있음 / 편집 중 / 저장됨 상태
- `구조화 저장소`
  - Story Bible / Canon / Release Policy 경로와 기준선 존재 여부 요약

이 요약은 기존 `field_stats`, `build_project_field_panels(...)`, `build_canon_store_summary(...)`, `build_release_policy_summary(...)`를 재사용해서 계산한다.

### 2. 주요 경고 / 다음 작업

상단 요약 아래에 `주요 경고 / 다음 작업` 섹션을 둔다.

예시:

- Story Bible이 비어 있습니다.
- State가 너무 길어 prompt budget을 압박하고 있습니다.
- Previous Summary가 비어 있어 최근 줄거리 맥락이 약합니다.

그리고 이에 대응하는 권장 작업을 flat list로 보여준다.

- Story Bible 초안을 먼저 작성하세요.
- State를 요약 버튼으로 압축하세요.
- Previous Summary 제안 생성을 사용해 최근 줄거리 기준선을 채우세요.

이번 slice에서는 버튼형 quick action까지는 넣지 않고, 텍스트 가이드만 둔다.

### 3. 고급 편집 섹션

기존 네 문서 편집기는 `고급 편집` 섹션 아래로 내린다.

- 기존 expander 구조 유지
- 현재처럼 attention 문서가 먼저 열리는 동작 유지
- 저장 로직과 text assist 로직은 유지

즉 이번 slice는 저장 동작을 바꾸지 않는다. 화면의 정보 구조만 바꾼다.

### 4. PREVIOUS SUMMARY 유지

`PREVIOUS SUMMARY`는 이번 slice에서 같은 탭 안에 유지한다.

다만 상단 상태 요약에서 현재 상태를 먼저 보여준다.

- 저장본이 비어 있으면 `비어 있음`
- 편집기에 unsaved text가 있으면 `편집 중`
- 저장본이 있고 편집기와 같으면 `저장됨`

하단 expander의 기존 AI 제안 / 저장 동작은 그대로 둔다.

### 5. 하단 도구 재정렬

하단 도구는 순서를 다음처럼 정리한다.

1. `고급 편집`
2. `PREVIOUS SUMMARY`
3. `구조화 저장소 현황`
4. `등장인물 JSON 관리`
5. `고급: 진단 / 실행 기록`

즉 `프로젝트 기준선 점검 -> 편집 -> 부가 도구` 흐름으로 읽히게 만든다.

## Boundaries

이번 slice의 범위:

- `ui/workspace.py`의 `render_project_settings_tab(...)` 정보 구조 재배치
- 상태 요약 계산 helper 추가
- 관련 UI 테스트 추가/수정

이번 slice의 비목표:

- Story Bible / State 저장 경계 변경
- `PREVIOUS SUMMARY` 저장 방식 변경
- 새 백엔드 저장소 추가
- 등장인물 관리 기능 확장
- diagnostics 패널 기능 변경

## Testing

다음 동작을 테스트로 잠근다.

1. 상단 상태 snapshot이 핵심 문서 준비도와 attention count를 올바르게 계산하는지
2. `PREVIOUS SUMMARY` 상태가 `비어 있음 / 편집 중 / 저장됨`으로 구분되는지
3. 경고/권장 작업이 비어 있는 문서와 초과 문서를 기준으로 생성되는지
4. 기존 편집기와 `PREVIOUS SUMMARY`, 구조화 저장소, 캐릭터, 진단 패널이 여전히 렌더 경로에 남아 있는지

## Expected Outcome

이 변경 후 `[1] 프로젝트 통합 설정`은 더 이상 긴 편집 폼부터 보여주는 탭이 아니라,

- 작품 기준선이 지금 어떤 상태인지 먼저 보여주고
- 무엇을 먼저 손봐야 할지 알려주며
- 필요할 때 기존 편집기로 내려가 수정하는

`상태 우선 설정 허브`가 된다.
