# Workspace Structured Store Boundary Design

## 배경

현재 `_2`는 생성과 발행 경계에서는 `StoryBibleStore`, `CanonStore`, `ReleasePolicyStore`를 이미 도입했다. 하지만 `프로젝트 통합 설정` 탭은 아직 `config.json` 중심 사고에 머물러 있다.

- `ui/workspace.py`는 네 개 핵심 문서를 `generator.ctx.get_config()`로 읽고 `save_config()`로 한 번에 저장한다.
- `ContextManager.get_config()`는 `StoryBibleStore`를 병합해 보여 주지만, UI 경계에서는 여전히 `config.json`이 기준처럼 보인다.
- `CanonStore`와 `ReleasePolicyStore`는 생성 프롬프트에는 반영되지만, 워크스페이스 UI에는 거의 드러나지 않는다.

이 상태는 새 아키텍처를 도입했는데도 사용자가 레거시 저장 경계를 계속 밟게 만든다.

## 목표

이번 단계의 목표는 세 가지다.

1. `프로젝트 통합 설정` 탭에서 `STORY_BIBLE / STYLE_GUIDE / CONTINUITY` 저장을 `StoryBibleStore` 직접 저장으로 전환한다.
2. 같은 탭에서 `STATE`와 `PREVIOUS SUMMARY`는 전용 저장 경로로 분리한다.
3. 같은 탭에서 `CanonStore`와 `ReleasePolicyStore`를 읽기 전용 요약으로 드러내 구조화 저장소가 기준선임을 UI에서 확인할 수 있게 한다.

## 선택지

### 옵션 1. Workspace 경계만 얇게 교체

- `ContextManager`에 워크스페이스 전용 snapshot/save helper를 추가한다.
- `ui/workspace.py`는 새 helper를 사용한다.
- `Canon`과 `Release Policy`는 읽기 전용 요약만 노출한다.

장점:
- 현재 탭 구조를 거의 유지한다.
- 다른 탭을 건드리지 않고도 `config.json` 중심 저장 흐름을 줄일 수 있다.
- 테스트 범위를 비교적 작게 유지할 수 있다.

단점:
- 다른 탭은 당분간 `get_config()` 병합 경로를 계속 사용한다.

### 옵션 2. 프로젝트 설정 탭을 구조화 저장소 허브로 재구성

- `Story Bible`, `Canon`, `Release Policy`, `State`를 별도 대형 섹션으로 재배치한다.

장점:
- 새 아키텍처가 가장 명확하다.

단점:
- UI 변화가 커서 이번 단계 범위를 넘긴다.
- Streamlit 상태와 테스트 갱신 범위가 커진다.

### 옵션 3. ContextManager 내부만 확장하고 UI는 거의 유지

- `save_config()`는 유지하되 내부에서 저장소 분기를 더 많이 담당하게 한다.

장점:
- 변경량이 가장 적다.

단점:
- UI에서는 여전히 `config.json`이 기준처럼 보인다.
- 새 경계를 쓰는 이유가 흐려진다.

이번 단계는 옵션 1을 채택한다.

## 설계

### 1. ContextManager에 워크스페이스 전용 경계 추가

`ContextManager`에는 다음 성격의 전용 메서드를 추가한다.

- `get_workspace_settings()`
  - 워크스페이스 탭이 필요로 하는 `worldview`, `tone_and_manner`, `continuity`, `state`, `summary_of_previous`를 반환한다.
  - `StoryBibleStore` 값은 직접 읽고, `state/summary/plot`은 레거시 config에서 읽는다.
- `save_story_bible_sections(...)`
  - `StoryBibleStore`를 직접 갱신한다.
  - 레거시 호환을 위해 `config.json`의 대응 필드도 동기화한다.
- `save_state(...)`
  - `state`만 저장한다.
- `save_previous_summary(...)`
  - `summary_of_previous`만 저장한다.

핵심은 `workspace.py`가 더 이상 전체 config dict를 수정한 뒤 `save_config()`에 의존하지 않게 만드는 것이다.

### 2. Workspace UI 저장 경계 교체

`ui/workspace.py`는 워크스페이스 탭에서 다음 규칙을 사용한다.

- 네 개 핵심 필드 표시용 데이터는 `get_workspace_settings()`에서 읽는다.
- `STORY_BIBLE`, `STYLE_GUIDE`, `CONTINUITY` 저장 버튼은 `save_story_bible_sections(...)`를 사용한다.
- `STATE`는 `save_state(...)`를 사용한다.
- `PREVIOUS SUMMARY`는 `save_previous_summary(...)`를 사용한다.
- AI 보조 버튼도 해당 필드의 저장 경계만 호출한다.

이렇게 하면 Story Bible 관련 편집이 구조화 저장소를 직접 기준으로 삼는다.

### 3. Canon / Release Policy 읽기 전용 요약 노출

워크스페이스 탭 하단 또는 별도 expander에 구조화 저장소 요약을 추가한다.

- `Canon current_state`
  - `people`, `resources`, `hooks`, `timeline` 개수와 저장 경로를 보여 준다.
- `Release Policy`
  - global 기본 정책과 활성 플랫폼 목록을 요약한다.

이번 단계에서는 편집 기능을 넣지 않는다. 이유는 release policy 편집은 발행 탭과 연계되어야 하고, canon은 publish 성공 후 구조화 후보를 통해 갱신되는 경계가 더 중요하기 때문이다.

### 4. Session 초기화 경로 정리

프로젝트 전환 시 textarea 초기값을 채우는 `load_project_textareas(...)`는 `get_config()` 병합 결과 대신 워크스페이스 snapshot을 받도록 바꾼다.

이 변경은 워크스페이스 탭의 초기 표시값이 구조화 저장소 기준임을 더 명확히 한다.

### 5. 테스트 전략

필수 테스트는 세 묶음이다.

- `ContextManager`
  - workspace snapshot이 structured story bible + legacy state/summary를 섞어 반환하는지
  - story bible 전용 저장이 `StoryBibleStore`와 legacy config를 함께 동기화하는지
  - state/summary 전용 저장이 의도한 필드만 바꾸는지
- `ui.workspace` helper
  - `Canon` / `Release Policy` 요약 helper가 예상 포맷을 만드는지
- `ui.app`
  - `load_project_textareas`가 workspace snapshot 입력에도 동작하는지

## 비목표

이번 단계에서 하지 않는 것:

- 다른 탭의 `config.json` 의존성 제거
- release policy 편집 UI 추가
- canon 직접 편집 UI 추가
- `config.json` 삭제

## 완료 기준

다음이 만족되면 이번 단계는 완료다.

1. 워크스페이스 탭 저장 동작이 `save_config()` 일괄 저장 대신 전용 경계를 사용한다.
2. Story Bible 3개 필드는 `StoryBibleStore` 직접 저장을 기준으로 동작한다.
3. `STATE`와 `PREVIOUS SUMMARY`는 전용 저장 경계로 분리된다.
4. 워크스페이스 UI에서 `CanonStore`와 `ReleasePolicyStore`의 현재 상태를 읽기 전용으로 확인할 수 있다.
5. 관련 단위 테스트와 회귀 테스트가 통과한다.
