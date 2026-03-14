# Context And Budget Boundary Design

## 배경

`workspace`와 `chapters` 탭은 이제 `STATE / PREVIOUS SUMMARY` 저장 경계를 대부분 분리했다. 하지만 내부 `ContextManager`와 토큰 예산 읽기 경계에는 아직 레거시 `config.json` 중심 흐름이 남아 있다.

- `ContextManager.update_summary()`는 새 요약 텍스트를 만든 뒤 `get_config()`와 `save_config()`를 통해 전체 config를 다시 저장한다.
- `ContextManager.apply_context_updates()`도 `state`와 `summary_of_previous`만 바꾸면서 전체 config snapshot을 다시 저장한다.
- `ContextManager.update_worldview()`는 Story Bible 일부만 바꾸고 싶어도 전체 config 경로를 사용한다.
- `ui/chapters.py`의 토큰/비용 패널은 예산 계산용으로 `generator.ctx.get_config()` 전체 snapshot을 읽는다.
- `core/token_budget.py`는 사실상 `workspace`의 5개 핵심 필드만 필요하지만, 코드 상으로는 “아무 config dict”를 받는 것처럼 보인다.

이 상태는 쓰기 경계와 읽기 경계가 각각 아직 레거시 모델을 전제하게 만든다. 다음 단계에서 `config.json`을 호환 저장소로 밀어내려면 이 중간 경계를 먼저 정리해야 한다.

## 목표

이번 단계의 목표는 세 가지다.

1. `ContextManager`의 남은 레거시 갱신 메서드가 전용 저장 메서드를 재사용하도록 정리한다.
2. 토큰/비용 예산 계산이 `workspace` 기준 5개 핵심 필드를 읽는다는 점을 코드 경계로 분명히 한다.
3. UI 동작과 기존 회귀를 유지하면서, `config.json` 전체 재저장을 한 단계 더 줄인다.

## 선택지

### 옵션 1. `ContextManager` 레거시 쓰기 메서드만 정리

- `update_summary`, `apply_context_updates`, `update_worldview`만 전용 저장 메서드로 바꾼다.

장점:
- 내부 쓰기 경계가 더 일관된다.

단점:
- 토큰 예산 읽기 쪽은 여전히 `get_config()` 전제에 머문다.

### 옵션 2. `token budget` 읽기 경계만 정리

- `core/token_budget.py`와 `ui/chapters.py`만 `workspace snapshot` 기준으로 읽게 바꾼다.

장점:
- 읽기 경계는 깔끔해진다.

단점:
- 내부 레거시 쓰기 메서드는 그대로 남아 구조가 반쯤만 정리된다.

### 옵션 3. 내부 쓰기 경계와 token budget 읽기 경계를 같이 정리

- `ContextManager` 레거시 갱신 메서드는 전용 저장 메서드를 재사용한다.
- `token budget`은 `workspace snapshot` 기준 읽기로 의미를 명확히 한다.

장점:
- 읽기와 쓰기 경계가 같이 정리된다.
- 다음 단계에서 `config.json`을 더 뒤로 밀어내기 쉬워진다.

단점:
- 옵션 1, 2보다 손대는 파일이 조금 더 많다.

이번 단계는 옵션 3을 채택한다.

## 설계

### 1. `ContextManager` 레거시 갱신 메서드 재배선

다음 메서드는 내부에서 전용 저장 경계를 재사용하도록 바꾼다.

- `update_summary(new_summary, generator_instance=None)`
  - 요약 텍스트를 계산한 뒤 `save_previous_summary(...)`를 호출한다.
- `apply_context_updates(state=None, summary_of_previous=None)`
  - 기존처럼 backup/applied/current 구조는 유지한다.
  - 실제 저장은 `save_state(...)`와 `save_previous_summary(...)`를 통해 수행한다.
- `update_worldview(new_worldview)`
  - 현재 Story Bible snapshot을 읽고, `save_story_bible_sections(...)`로 필요한 필드만 유지하면서 `worldview`만 갱신한다.

핵심은 public API를 유지하면서 내부 저장 경계를 전용 메서드 기준으로 통일하는 것이다.

### 2. `token budget`의 입력 경계 명확화

`core/token_budget.py`는 현재도 사실상 다음 5개 필드만 사용한다.

- `worldview`
- `tone_and_manner`
- `continuity`
- `state`
- `summary_of_previous`

이번 단계에서는 helper 시그니처는 유지해도 괜찮지만, 코드와 테스트에서는 이것이 “workspace snapshot”을 받는 함수라는 점을 명확히 한다.

가능한 방식:

- local helper 이름 추가
  - 예: `_normalize_workspace_budget_fields(snapshot)`
- 또는 기존 함수 문맥 정리
  - 호출부가 `get_workspace_settings()` 결과를 넘기도록 고정

중요한 점은 plot이나 기타 legacy 필드를 예산 계산 경계에 섞지 않는 것이다.

### 3. `ui/chapters.py` 토큰 예산 패널 읽기 경계 수정

현재 `render_generation_budget_panel(...)`은:

- `generator.ctx.get_config()`
- `get_field_stats(...)`
- `get_budget_recommendations(...)`

를 사용한다.

이 경계는 다음처럼 바꾼다.

- 예산 및 길이 가이드: `generator.ctx.get_workspace_settings()`
- plot 관련 실제 프롬프트 계산: 기존 `build_generation_prompt(...)` 유지

즉 “예산/길이 가이드”는 workspace 5개 필드 기준으로 보고, plot은 별도로 prompt 계산 시점에만 다룬다.

### 4. 테스트 전략

필수 테스트는 세 묶음이다.

- `tests/test_context_manager.py`
  - `update_summary()`가 결과적으로 summary 전용 저장 경계를 통해 동작하는지
  - `apply_context_updates()`가 state/summary만 바꾸고 backup/current 구조를 유지하는지
  - `update_worldview()`가 Story Bible의 다른 필드를 보존하는지
- `tests/test_ui_helpers.py`
  - 필요하면 budget snapshot helper 또는 관련 contract를 pure helper 수준에서 검증
- 기존 origin regression
  - `tests.test_context_manager`
  - `tests.test_ui_helpers`
  - `tests.test_automator`
  - `tests.test_publishing_runtime`

이번 단계에서는 Streamlit 렌더링보다 helper와 context contract 회귀에 집중한다.

## 비목표

이번 단계에서 하지 않는 것:

- `config.json` 삭제
- plot 저장 경계 변경
- `automation` / `publishing` UI 변경
- token budget API의 대규모 rename

## 완료 기준

다음이 만족되면 이번 단계는 완료다.

1. `ContextManager`의 남은 레거시 갱신 메서드가 전용 저장 경계를 재사용한다.
2. `ui/chapters.py` 토큰 예산 패널은 workspace snapshot 기준으로 길이 가이드를 계산한다.
3. 관련 단위 테스트와 기존 origin regression이 통과한다.
