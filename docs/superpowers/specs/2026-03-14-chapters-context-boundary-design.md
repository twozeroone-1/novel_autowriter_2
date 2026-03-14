# Chapters Context Boundary Design

## 배경

`workspace` 탭은 이제 `Story Bible` 3필드와 `STATE / PREVIOUS SUMMARY` 저장 경계를 구조화 저장소 기준으로 분리했다. 하지만 생성, 검수, 반자동 실행이 모인 `ui/chapters.py`는 아직 `config.json` 중심 흐름을 강하게 유지하고 있다.

- 생성 탭의 컨텍스트 제안 반영은 `generator.ctx.apply_context_updates(...)`를 쓰지만, 기본값 계산은 여전히 `get_config()`에 기대고 있다.
- 검수 탭의 컨텍스트 반영도 같은 패턴을 반복한다.
- 반자동 탭은 최종 저장 시 `current_config["state"]`와 `current_config["summary_of_previous"]`를 수정한 뒤 `save_config()`로 통째 저장한다.

이 상태는 사용자 입장에서 같은 `STATE / PREVIOUS SUMMARY`를 다루는데도 탭마다 저장 경계가 다르게 보이게 만든다. 또한 반자동 탭은 state/summary만 바꾸고도 불필요하게 전체 config dict를 다시 저장한다.

## 목표

이번 단계의 목표는 세 가지다.

1. `ui/chapters.py`에서 `STATE / PREVIOUS SUMMARY` 반영 경계를 전용 저장 메서드 기준으로 통일한다.
2. 생성 탭, 검수 탭, 반자동 탭이 같은 규칙으로 현재값 읽기와 저장을 수행하게 만든다.
3. `config.json` 전체 덮어쓰기를 줄이되, 생성/검수/반자동 동작과 기존 테스트는 그대로 유지한다.

## 선택지

### 옵션 1. `chapters` 탭의 컨텍스트 저장 경계만 먼저 교체

- `ui/chapters.py` 안에 순수 helper를 두고 `state / summary` 저장을 전용 메서드로 라우팅한다.
- 읽기 기본값은 목적에 맞게 `get_workspace_settings()` 또는 `get_config()`를 선택해 사용한다.

장점:
- 범위가 작고 회귀 위험이 낮다.
- 사용자가 가장 자주 밟는 생성/검수/반자동 흐름의 저장 경계를 바로 정리할 수 있다.

단점:
- `ContextManager`의 레거시 호환 메서드들은 당분간 남는다.

### 옵션 2. `chapters`와 `ContextManager`를 한 번에 크게 정리

- `apply_context_updates`, `update_summary`, `update_worldview` 등 레거시 메서드를 다시 설계한다.

장점:
- 내부 구조가 더 정리된다.

단점:
- 자동화/리뷰어/생성기까지 영향 범위가 넓어진다.
- 이번 하위 단계 범위를 넘길 가능성이 높다.

### 옵션 3. 남은 UI 전체를 한 번에 구조화 저장소 기준으로 전환

- `chapters`, `automation`, `publishing`까지 함께 정리한다.

장점:
- 큰 그림은 빨리 맞춰진다.

단점:
- 회귀 범위가 너무 커서 현재 작업 흐름과 맞지 않는다.

이번 단계는 옵션 1을 채택한다.

## 설계

### 1. `ui/chapters.py`에 순수 저장 라우터 추가

`workspace.py`와 같은 성격의 helper를 `ui/chapters.py`에도 둔다.

- `persist_chapter_context_update(...)`
  - `state`와 `summary_of_previous`를 각각 전용 경계로 저장한다.
- 필요하면 `build_chapter_context_defaults(...)`
  - AI 제안값이 없을 때 현재 프로젝트 값을 안전하게 fallback 한다.

핵심은 Streamlit 버튼 핸들러가 dict를 직접 수정하지 않고, 저장 의도를 helper에 넘기게 만드는 것이다.

### 2. 생성 탭 / 검수 탭 컨텍스트 반영 정리

생성 탭과 검수 탭은 이미 `apply_context_updates(...)`를 사용한다. 이번 단계에서는 다음만 정리한다.

- 기본값 계산에 사용하는 현재 프로젝트 snapshot을 의도적으로 읽는다.
- `state`와 `summary_of_previous` 반영 버튼은 공통 helper를 거친다.
- UI 동작은 유지한다. 즉 사용자는 여전히 텍스트를 검토하고 저장 버튼을 누른다.

이 단계에서는 UX 자체를 바꾸지 않는다.

### 3. 반자동 탭의 `save_config()` 전체 저장 제거

현재 반자동 탭은 실행 결과를 검토한 뒤:

- `current_config["state"] = ...`
- `current_config["summary_of_previous"] = ...`
- `save_config(current_config)`

를 수행한다.

이 경계는 다음으로 바꾼다.

- `persist_chapter_context_update(...)`
  - 내부에서 `save_state(...)`
  - 내부에서 `save_previous_summary(...)`

이렇게 하면 반자동 탭이 state/summary만 바꾸고도 Story Bible 또는 다른 legacy 필드를 다시 저장하지 않게 된다.

### 4. 읽기 경계 원칙

이번 단계에서는 읽기 경계를 다음처럼 둔다.

- `worldview / tone / continuity / state / summary` 전체 snapshot이 필요할 때: `get_workspace_settings()`
- plot이나 기타 legacy 필드가 필요할 때: `get_config()` 유지

즉 `chapters` 탭의 컨텍스트 반영 UI는 가급적 `get_workspace_settings()`를 우선 사용하되, 기존 plot 흐름은 그대로 둔다.

### 5. 테스트 전략

필수 테스트는 두 묶음이다.

- `tests/test_ui_helpers.py`
  - chapter context helper가 `save_state`와 `save_previous_summary`를 올바르게 라우팅하는지
  - current-value fallback helper가 제안값 우선/현재값 fallback 규칙을 유지하는지
- 기존 origin pipeline 회귀
  - `tests.test_context_manager`
  - `tests.test_automator`
  - `tests.test_publishing_runtime`
  - `tests.test_ui_helpers`

이번 단계에서는 Streamlit 렌더링 자체를 깊게 테스트하지 않고, pure helper와 기존 회귀로 안정성을 확보한다.

## 비목표

이번 단계에서 하지 않는 것:

- `ContextManager` 레거시 API 삭제
- `Reviewer`나 `Generator` 프롬프트 구조 변경
- `automation` / `publishing` UI 경계 변경
- `config.json` 제거

## 완료 기준

다음이 만족되면 이번 단계는 완료다.

1. 생성/검수/반자동 탭의 context 반영이 공통 저장 경계를 사용한다.
2. 반자동 탭은 더 이상 state/summary 반영을 위해 `save_config()`로 전체 config를 덮어쓰지 않는다.
3. 관련 helper 테스트와 기존 origin pipeline 회귀가 통과한다.
