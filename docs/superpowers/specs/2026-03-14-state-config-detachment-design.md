# State Config Detachment Design

## 배경

최근 단계에서 [context_state_store.py](/mnt/c/Users/W/novel_autowriter_2/core/context_state_store.py)를 추가해서 `state`와 `summary_of_previous`의 실제 저장 기준선을 `ContextStateStore`로 옮겼다.

- `save_state(...)`는 이제 state store를 갱신한다.
- `save_previous_summary(...)`도 state store를 갱신한다.
- `_get_state_snapshot()`은 state store를 우선 읽는다.
- `get_workspace_settings()`도 state store 기준으로 snapshot을 조립한다.

하지만 일반 config 계약은 아직 절반쯤 레거시다.

- [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)의 `save_config(...)`는 여전히 `state`와 `summary_of_previous`를 일반 config 필드처럼 받아서 `config.json`에 저장한다.
- 테스트도 아직 `save_config({... "state": ..., "summary_of_previous": ...})` 패턴을 많이 사용한다.
- 즉 실제 source of truth는 state store인데, 일반 config write 계약은 아직 그 사실을 숨긴다.

이 상태는 기능상 당장 문제를 일으키진 않지만, 저장 경계가 다시 흐려진다. Story Bible과 plot은 이미 “전용 save API만 본 저장 경계”라는 규칙을 갖고 있는데, state만 예외처럼 남는다.

## 목표

이번 단계의 목표는 세 가지다.

1. `save_config(...)`가 더 이상 `state`와 `summary_of_previous`를 본 저장 필드처럼 다루지 않게 만든다.
2. state write 경계를 `save_state(...)` / `save_previous_summary(...)` / `apply_context_updates(...)`로 명확히 고정한다.
3. `get_config()`는 당분간 merged compatibility view로 유지한다.

## 선택지

### 옵션 1. 현 상태 유지

- source of truth는 state store지만, `save_config(...)`는 계속 state/summary를 일반 config처럼 받는다.

장점:
- 구현 비용이 없다.

단점:
- write contract가 모순된다.
- 호출부와 테스트가 잘못된 저장 경계를 계속 학습한다.
- 이후 config 제거 단계가 늦어진다.

### 옵션 2. write contract만 분리하고 read compatibility는 유지

- `save_config(...)`에서는 state/summary를 저장 대상으로 취급하지 않는다.
- `get_config()`는 계속 merged view를 반환한다.
- 전용 state save API만 writer로 남긴다.

장점:
- 범위가 작고 안전하다.
- 기존 UI/reader 흐름을 크게 흔들지 않는다.
- 다음 단계에서 `DEFAULT_CONFIG`와 compatibility view를 더 정리하기 쉬워진다.

단점:
- `get_config()`에는 여전히 state/summary가 보인다.

### 옵션 3. 일반 config 계약에서 state를 전면 제거

- `DEFAULT_CONFIG`, `get_config()`, 테스트, helper 전부에서 state/summary를 걷어낸다.

장점:
- 장기적으로 가장 깔끔하다.

단점:
- 범위가 크다.
- 테스트와 helper 다수를 동시에 흔든다.
- 이번 단계에서 필요한 것보다 훨씬 크다.

이번 단계는 옵션 2를 채택한다.

## 설계

### 1. `save_config(...)` 역할 축소

[context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)의 `save_config(...)`는 이제 일반 workspace compatibility writer로만 남긴다.

이번 단계 이후 `save_config(...)`가 책임질 필드:

- `worldview`
- `tone_and_manner`
- `continuity`

반대로 다음 필드는 `save_config(...)`의 본 저장 대상에서 제외한다.

- `state`
- `summary_of_previous`

즉 호출부가 이 값을 넘기더라도:

- state store를 덮어쓰지 않는다.
- state shadow도 직접 갱신하지 않는다.
- Story Bible 저장과 legacy config normalization만 수행한다.

핵심은 “state를 저장하고 싶다면 전용 API를 써야 한다”는 규칙을 코드 계약으로 만드는 것이다.

### 2. compatibility read는 유지

이번 단계에서 `get_config()`는 유지한다.

역할은 그대로다.

- Story Bible 값은 structured store에서 읽어 합친다.
- state/summary는 ContextStateStore snapshot을 합쳐 보여 준다.

즉 `get_config()`는 여전히 “현재 합쳐진 보기”를 제공하지만, 그것이 writer API를 정당화하지는 않는다.

이 분리가 중요하다.

- `get_config()`는 read compatibility
- `save_config()`는 Story Bible compatibility write

둘의 범위를 일부러 비대칭으로 둔다.

### 3. `DEFAULT_CONFIG`는 당장 유지

이번 단계에서는 `DEFAULT_CONFIG`에서 `state`와 `summary_of_previous`를 제거하지 않는다.

이유:

- `_normalize_config(...)`와 legacy fallback은 아직 이 기본값 구조를 사용한다.
- 한 단계에 read contract와 write contract를 같이 흔들면 범위가 커진다.

즉 이번 단계는 write detachment만 한다.

### 4. 권장 저장 경계 정리

이번 단계 후 권장 writer는 다음처럼 고정된다.

- Story Bible
  - `save_story_bible_sections(...)`
  - 또는 제한적 compatibility writer인 `save_config(...)`

- state
  - `save_state(...)`
  - `save_previous_summary(...)`
  - `apply_context_updates(...)`
  - `update_summary(...)`

- plot
  - `save_plot_outline(...)`

즉 `save_config(...)`는 “모든 걸 넣는 만능 setter”가 아니게 된다.

### 5. 테스트 전략

이번 단계의 테스트는 write contract를 증명해야 한다.

필수 테스트 방향:

- [test_context_manager.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_context_manager.py)
  - `save_config(...)`가 state/summary를 넘겨받아도 ContextStateStore 값을 덮어쓰지 않는지
  - `save_config(...)`가 state shadow를 직접 바꾸지 않는지
  - `get_config()`는 여전히 merged state/summary를 보여 주는지

권장 테스트 예시:

- `ContextStateStore`에 먼저 `stored state`, `stored summary` 저장
- `save_config(...)`에 다른 `state` / `summary_of_previous`를 전달
- 이후:
  - state store 값은 그대로인지 확인
  - `get_config()`는 store 기준 merged 값을 반환하는지 확인
  - `config.json` raw payload는 Story Bible만 바뀌고 state shadow는 그대로인지 확인

이렇게 해야 “read는 compatibility, write는 detachment”가 명확히 증명된다.

### 6. 호출부 정리 범위

이번 단계에서 production UI 호출부는 크게 바꾸지 않아도 된다.

이유:

- 최근 단계들에서 UI는 이미 `save_state(...)` / `save_previous_summary(...)` 위주로 라우팅되고 있다.
- 문제의 핵심은 주로 `ContextManager.save_config(...)` 계약과 일부 테스트 습관이다.

따라서 우선순위는:

1. `ContextManager` write contract 정리
2. 관련 테스트를 새 계약 기준으로 정리

UI 리팩터링은 이 단계의 부수 효과가 아니다.

### 7. 비목표

이번 단계에서 하지 않는 것:

- `get_config()` 제거
- `DEFAULT_CONFIG`에서 state/summary 제거
- `config.json` shadow 자체 제거
- Story Bible compatibility writer 제거
- UI 레이아웃 변경
- automation/publishing store 계약 변경

## 완료 기준

다음이 만족되면 이번 단계는 완료다.

1. `save_config(...)`가 더 이상 `state`와 `summary_of_previous`를 본 저장 필드처럼 다루지 않는다.
2. state writer는 전용 API 경계만 사용한다.
3. `get_config()`는 계속 merged compatibility view를 유지한다.
4. 관련 단위 테스트와 기존 origin 회귀가 통과한다.
