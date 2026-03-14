# State Read Detachment Design

## 배경

최근 단계들로 state 경계는 상당 부분 정리됐다.

- `state`와 `summary_of_previous`의 writer는 [context_state_store.py](/mnt/c/Users/W/novel_autowriter_2/core/context_state_store.py) 기준으로 이동했다.
- [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)의 `save_state(...)`, `save_previous_summary(...)`, `apply_context_updates(...)`는 전용 경계를 사용한다.
- 일반 config writer인 `save_config(...)`는 더 이상 state/summary를 본 저장 필드처럼 다루지 않는다.

하지만 read 계약은 아직 절반쯤 레거시다.

- [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)의 `get_config()`는 아직 `state`와 `summary_of_previous`를 merged compatibility view로 노출한다.
- `DEFAULT_CONFIG`도 여전히 Story Bible 필드와 state 필드를 한 객체로 묶고 있다.
- production UI는 대부분 [workspace.py](/mnt/c/Users/W/novel_autowriter_2/ui/workspace.py), [chapters.py](/mnt/c/Users/W/novel_autowriter_2/ui/chapters.py), [app.py](/mnt/c/Users/W/novel_autowriter_2/ui/app.py)에서 `get_workspace_settings()`를 쓰는데, 테스트는 아직 `get_config()`를 “전체 workspace snapshot”처럼 보는 경우가 남아 있다.

즉 write contract는 분리됐지만 read contract는 아직 `get_config()`와 `DEFAULT_CONFIG`에 state가 섞여 있어서, 일반 config와 workspace snapshot의 경계가 완전히 분리되지 않았다.

## 목표

이번 단계의 목표는 세 가지다.

1. `get_config()`에서 `state`와 `summary_of_previous`를 일반 config read 계약에서 분리한다.
2. `get_workspace_settings()`를 state/summary를 포함한 유일한 workspace snapshot API로 고정한다.
3. `DEFAULT_CONFIG`도 Story Bible 중심 기본값으로 축소하고, state 기본값은 `ContextStateStore` 기준으로만 다룬다.

## 선택지

### 옵션 1. 현 상태 유지

- writer만 분리하고, `get_config()`는 계속 state/summary를 포함한다.

장점:
- 구현 비용이 없다.

단점:
- read contract가 계속 헷갈린다.
- 테스트와 future caller가 `get_config()`를 전체 workspace snapshot처럼 계속 쓸 가능성이 높다.
- `config.json` compatibility layer 축소가 더뎌진다.

### 옵션 2. read contract만 분리하고 workspace snapshot API는 유지

- `get_config()`는 Story Bible 호환 read API로 축소한다.
- `get_workspace_settings()`는 state/summary를 계속 포함한다.
- state 기본값은 `ContextStateStore` 전용 기본값으로 다룬다.

장점:
- 범위가 작고 안전하다.
- production UI 흐름과 이미 맞아 있다.
- 일반 config 계약과 workspace snapshot 계약을 명확히 나눌 수 있다.

단점:
- 테스트와 일부 fake context를 같이 정리해야 한다.

### 옵션 3. `get_config()` 제거

- `get_config()`를 없애거나 대규모 rename을 수행한다.

장점:
- 장기적으로 가장 깔끔하다.

단점:
- 범위가 크다.
- 호환성 비용이 높다.
- 이번 단계에서 필요한 것보다 과하다.

이번 단계는 옵션 2를 채택한다.

## 설계

### 1. `get_config()` 역할 축소

[context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)의 `get_config()`는 이후 Story Bible compatibility read API로만 남긴다.

즉 반환 범위는 다음 세 필드만 보장한다.

- `worldview`
- `tone_and_manner`
- `continuity`

반대로 다음 두 필드는 더 이상 `get_config()` 계약에 포함하지 않는다.

- `state`
- `summary_of_previous`

핵심은 `get_config()`를 “일반 config view”로 되돌리고, workspace snapshot 역할을 뺀다는 점이다.

### 2. `get_workspace_settings()`를 workspace snapshot의 기준선으로 고정

[context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)의 `get_workspace_settings()`는 그대로 유지하되, 역할을 더 분명히 한다.

- Story Bible 필드
- `state`
- `summary_of_previous`

를 함께 반환하는 유일한 공용 snapshot API다.

즉 이후 규칙은 명확하다.

- Story Bible만 보면 `get_config()`
- 전체 workspace snapshot이 필요하면 `get_workspace_settings()`

production code는 이미 대부분 이 형태를 따르고 있으므로, 이번 단계는 실제 동작보다 계약 정리의 성격이 강하다.

### 3. 기본값 분리

현재 [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)의 `DEFAULT_CONFIG`는 Story Bible과 state를 한 객체에 담고 있다.

이번 단계에서는 이를 분리한다.

권장 방향:

- `DEFAULT_CONFIG` 또는 후속 이름은 Story Bible compatibility 기본값만 담는다.
- state 기본값은 [context_state_store.py](/mnt/c/Users/W/novel_autowriter_2/core/context_state_store.py)의 `DEFAULT_CONTEXT_STATE`만 사용한다.

중요한 점은 같은 기본값을 두 군데서 중복 관리하지 않는 것이다.

### 4. 내부 helper 정리

다음 내부 경계도 함께 정리한다.

- `_normalize_config(...)`는 Story Bible 필드만 정규화한다.
- `_merge_state_snapshot_into_config(...)`는 제거하거나 `get_config()` 경로에서 더 이상 쓰지 않는다.
- `_ensure_default_files()`에서 `config.json` 초기화는 Story Bible compatibility 필드만 생성한다.

이렇게 하면 `config.json`과 `context_state.json`의 책임이 코드 수준에서도 분리된다.

### 5. legacy fallback은 유지

이번 단계에서도 state legacy fallback 자체는 유지한다.

즉 [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)의 `_get_state_snapshot()`는 계속:

- `context_state.json`이 있으면 store 우선
- 없으면 legacy `config.json`의 `state` / `summary_of_previous` fallback

으로 동작한다.

이건 기존 프로젝트를 깨지 않기 위한 compatibility layer다.

즉 이번 단계는 “public read contract 정리”이지, “legacy fallback 제거”는 아니다.

### 6. 테스트 전략

이번 단계의 테스트는 read contract 변경을 직접 증명해야 한다.

필수 테스트 방향:

- [test_context_manager.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_context_manager.py)
  - `get_config()`가 더 이상 `state` / `summary_of_previous`를 노출하지 않는지
  - `get_workspace_settings()`는 계속 state/summary를 노출하는지
  - state/summary를 확인하던 기존 테스트는 `get_workspace_settings()` 또는 전용 save API 기준으로 바뀌는지

- [test_ui_helpers.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_ui_helpers.py)
  - fake context가 state/summary를 읽어야 하는 경우 `get_workspace_settings()`를 기준으로 잡는지
  - `get_config()` 의존이 실제로 필요 없는 곳은 제거되는지

권장 새 테스트 예시:

- `test_get_config_does_not_expose_state_fields`
- `test_get_workspace_settings_includes_state_fields_from_context_state_store`

이렇게 해야 “일반 config”와 “workspace snapshot”의 계약 차이가 명확해진다.

### 7. 호출부 영향

이번 단계에서 production 호출부 영향은 제한적이다.

이유:

- [workspace.py](/mnt/c/Users/W/novel_autowriter_2/ui/workspace.py) 는 이미 `get_workspace_settings()`를 쓴다.
- [chapters.py](/mnt/c/Users/W/novel_autowriter_2/ui/chapters.py) 도 이미 `get_workspace_settings()`를 쓴다.
- [app.py](/mnt/c/Users/W/novel_autowriter_2/ui/app.py) 역시 sidebar bootstrap에 workspace snapshot을 사용한다.

즉 영향의 대부분은:

- `context.py`
- `test_context_manager.py`
- `test_ui_helpers.py`

에 집중된다.

### 8. 비목표

이번 단계에서 하지 않는 것:

- `get_config()` 제거
- legacy state shadow 제거
- `_get_state_snapshot()`의 legacy fallback 제거
- `config.json` 파일 자체 제거
- UI 레이아웃 변경
- automation/publishing store 계약 변경

## 완료 기준

다음이 만족되면 이번 단계는 완료다.

1. `get_config()`가 더 이상 `state`와 `summary_of_previous`를 노출하지 않는다.
2. `get_workspace_settings()`가 state/summary를 포함한 유일한 workspace snapshot API가 된다.
3. Story Bible 기본값과 state 기본값이 코드에서 분리된다.
4. 관련 단위 테스트와 기존 origin 회귀가 통과한다.
