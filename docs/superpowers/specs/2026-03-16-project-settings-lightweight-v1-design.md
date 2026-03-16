# Project Settings Lightweight V1 Design

## Goal

`작품 설정` 탭을 `기준선 관리 화면`으로 더 분명하게 만들고, 상단은 상태 요약과 권장 작업에 집중시키며 `PREVIOUS SUMMARY`, 구조화 저장소, 등장인물, 진단은 명확한 보조 섹션으로 내린다.

## Problem

현재 `작품 설정`은 이미 status-first 구조로 바뀌었지만, 아래에 `PREVIOUS SUMMARY`, 구조화 저장소, 등장인물, 진단이 같은 수준으로 길게 이어진다. 그 결과 사용자는 이 화면을 여전히 “긴 편집 탭”처럼 인식하기 쉽고, `운영 개요 -> 회차 워크플로 -> 발행 운영` 중심 구조가 흐려진다.

## Non-Goals

- `PREVIOUS SUMMARY` 기능 제거
- 구조화 저장소, 등장인물, 진단 기능 삭제
- `작품 설정`을 별도 다단계 위저드로 재구성
- `회차 워크플로` 또는 `발행 운영` 기능 변경

## Approaches Considered

### 1. 상단 요약만 조금 더 강화

가장 작은 변경이지만, 긴 하단 편집 구간은 그대로 남아서 화면 인상이 크게 달라지지 않는다.

### 2. Status-first 유지 + 보조 섹션 접기 강화

추천안이다. 상단은 `핵심 문서 준비도 / 경고 / 다음 작업`만 유지하고, 나머지는 `보조 관리` 아래로 묶는다. 현재 구조를 크게 깨지 않으면서도 화면 역할을 더 분명히 할 수 있다.

### 3. 작품 설정을 별도 단계형 화면으로 재설계

장기적으로는 가능하지만 이번 slice 범위를 넘는다. `workspace.py`와 테스트 변경이 지나치게 커진다.

## Recommended Design

### 1. 화면 역할 재정의

`작품 설정`은 매일 읽는 운영 화면이 아니라, 작품의 기준선을 유지하는 관리 화면으로 정의한다.

- 상단: `핵심 문서 준비도`, `확인 필요`, `PREVIOUS SUMMARY`, `구조화 저장소`
- 중단: `주요 경고 / 다음 권장 작업`
- 하단: `고급 편집`, `보조 관리`

### 2. 보조 관리 섹션 도입

기존의 아래 네 블록을 `2. 보조 관리` expander 안으로 이동한다.

- `PREVIOUS SUMMARY`
- `구조화 저장소 현황`
- `등장인물 JSON 관리`
- 진단 패널

이 expander는 기본적으로 접힌 상태로 두고, `PREVIOUS SUMMARY`가 비어 있거나 편집 중일 때만 확장한다.

### 3. PREVIOUS SUMMARY 역할 보강

`PREVIOUS SUMMARY`는 중요하지만 매일 직접 편집해야 하는 핵심 4문서와는 성격이 다르다. 따라서 상단 metric과 warning/action에는 남기되, 실제 편집기는 `보조 관리` 안으로 내린다.

보조 관리 안에서는 `PREVIOUS SUMMARY`를 첫 번째 보조 섹션으로 유지한다.

### 4. 문구 정리

상단 설명 문구는 “핵심 4문서가 기준선을 만든다”는 메시지에 집중한다. 하단 보조 섹션 쪽에는 “필요할 때만 여는 보조 관리”라는 설명을 추가한다.

## File Changes

- Modify: `ui/workspace.py`
  - `render_project_settings_tab(...)`를 `고급 편집`과 `보조 관리` 두 덩어리로 재구성
- Modify: `tests/test_ui_helpers.py`
  - 새 렌더 순서와 보조 섹션 진입점을 잠그는 테스트 추가

## Testing

- `render_project_settings_tab(...)`가 여전히 status metrics를 field editor보다 먼저 렌더링하는지 확인
- `보조 관리` expander 아래에서 `PREVIOUS SUMMARY`, 구조화 저장소, 등장인물, 진단이 렌더링되는지 확인
- `보조 관리` 라벨과 설명 문구가 기대대로 노출되는지 확인

## Risks

- Streamlit expander 추가로 widget key 충돌이 생길 수 있다.
- 보조 섹션이 너무 깊게 숨겨지면 기존 사용자에게 기능이 사라진 것처럼 보일 수 있다.

## Mitigations

- 기존 helper와 widget key는 그대로 유지하고, 감싸는 expander만 추가한다.
- 상단 `다음 권장 작업`과 `보조 관리` 설명 문구에서 `PREVIOUS SUMMARY`, 등장인물, 진단의 위치를 분명히 안내한다.
