# Story Bible API Detachment Design

## 배경

바로 직전 단계에서 [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)의 내부 helper는 `Story Bible shadow` 호환 계층이라는 의미를 갖도록 정리됐다.

현재 상태는 이렇다.

- `StoryBibleStore`가 source of truth다.
- `config.json`의 Story Bible 필드는 shadow copy다.
- `state` / `summary_of_previous`는 [context_state_store.py](/mnt/c/Users/W/novel_autowriter_2/core/context_state_store.py) 기준이다.
- `plot_outline` / `plot_version`는 [plot_store.py](/mnt/c/Users/W/novel_autowriter_2/core/plot_store.py) 기준이다.
- production UI는 대부분 `get_workspace_settings()`와 전용 저장 경계를 사용한다.

하지만 public API에는 아직 과거 이름이 남아 있다.

- `get_config()`
- `save_config(...)`
- `DEFAULT_CONFIG`

이제 이 이름들은 실제 의미와 잘 맞지 않는다.

- `get_config()`는 전체 config를 반환하지 않는다. Story Bible compatibility view만 반환한다.
- `save_config(...)`도 전체 config를 저장하지 않는다. Story Bible compatibility write만 수행한다.
- `DEFAULT_CONFIG` 역시 더 이상 일반 config default가 아니라 Story Bible shadow default다.

즉 내부 경계는 많이 정리됐지만, public API 이름은 아직 “옛날 의미”에 머물러 있다.

## 목표

이번 단계 목표는 네 가지다.

1. Story Bible용 public API를 이름상으로도 분명히 만든다.
2. `get_config()` / `save_config(...)` / `DEFAULT_CONFIG`를 compatibility alias로 한 단계 더 밀어낸다.
3. production code와 주요 테스트가 더 이상 generic `config` 개념에 기대지 않게 만든다.
4. 다음 단계에서 legacy compatibility API를 줄이거나 제거하기 쉽게 만든다.

## 선택지

### 옵션 1. 현 상태 유지

- 내부 helper만 정리된 상태로 둔다.

장점:
- 구현 비용이 없다.

단점:
- API 이름과 실제 의미가 계속 어긋난다.
- 새 호출부가 또 `get_config()` / `save_config()`를 사용하게 될 수 있다.
- 다음 제거 단계에서 migration 범위가 다시 넓어진다.

### 옵션 2. Story Bible 전용 public API를 추가하고 compatibility alias를 유지

- 예를 들어:
  - `get_story_bible_settings()`
  - `save_story_bible_settings(...)`
  - `DEFAULT_STORY_BIBLE_SETTINGS`
- `get_config()` / `save_config(...)` / `DEFAULT_CONFIG`는 당분간 alias로만 남긴다.

장점:
- 범위가 작고 안전하다.
- production caller를 점진적으로 새 이름으로 옮길 수 있다.
- 의미가 코드에서 바로 드러난다.

단점:
- compatibility alias와 새 API를 당분간 같이 유지해야 한다.

### 옵션 3. generic config API를 바로 제거

- `get_config()` / `save_config(...)` / `DEFAULT_CONFIG`를 바로 없앤다.

장점:
- 장기적으로 가장 깔끔하다.

단점:
- 지금은 범위가 너무 크다.
- 테스트와 hidden compatibility caller를 한 번에 많이 손봐야 한다.

이번 단계는 옵션 2를 채택한다.

## 설계

### 1. Story Bible 전용 public read API 추가

현재 `get_config()`는 사실상 Story Bible compatibility view다.

이번 단계에서는 이를 이름상으로도 분명히 하기 위해 전용 public reader를 추가한다.

권장 방향:

- `get_story_bible_settings()`
  - `worldview`
  - `tone_and_manner`
  - `continuity`

반환 계약은 지금의 `get_config()`와 동일하되, “Story Bible 전용 API”라는 의미가 드러나야 한다.

이후 `get_config()`는:

- thin alias
- 또는 compatibility wrapper

로만 남긴다.

핵심은 새 caller가 `get_config()` 대신 의미 있는 이름의 API를 사용하게 만드는 것이다.

### 2. Story Bible 전용 public write API 추가

지금 Story Bible 쓰기에는 이미:

- `save_story_bible_sections(...)`

가 있다. 하지만 이건 인자 구조가 강한 편이고, `save_config(...)`와 병행해서 보일 때 여전히 “config 저장” 개념이 남는다.

이번 단계에서는 다음 중 하나로 정리한다.

- `save_story_bible_settings(payload: dict)`
- 또는 기존 `save_story_bible_sections(...)`를 중심으로 두고 `save_config(...)`를 compatibility alias로 확정

추천은 첫 번째보다 두 번째다.

이유:

- 이미 `save_story_bible_sections(...)`가 production에서 잘 쓰이고 있다.
- 굳이 비슷한 public write API를 또 만들 필요는 없다.
- 대신 `save_config(...)`가 내부적으로 `save_story_bible_sections(...)` 혹은 같은 Story Bible shadow/write path로 위임된다는 사실을 더 분명히 하면 된다.

즉 이번 단계에서 핵심은 “write API를 하나 더 늘리는 것”보다 “generic write alias를 compatibility 위치로 내리는 것”이다.

### 3. 상수 이름도 Story Bible 의미를 드러내게 정리

현재 [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)의 `DEFAULT_CONFIG`는 alias로만 남아 있다.

이번 단계에서는 다음 규칙을 강화한다.

- 코드 내부 기본값 참조는 `DEFAULT_STORY_BIBLE_SHADOW` 또는 후속 이름을 사용한다.
- `DEFAULT_CONFIG`는 compatibility alias로만 남긴다.
- 테스트도 가능하면 Story Bible 의미를 가진 상수명을 우선 사용한다.

이렇게 하면 “DEFAULT_CONFIG는 더 이상 진짜 기본 계약이 아니다”라는 메시지가 분명해진다.

### 4. production 코드에서 generic config 개념 제거

production code 기준으로는 이미 많이 정리돼 있지만, 다음 규칙을 더 명확히 한다.

- Story Bible read가 필요하면 Story Bible 전용 API
- workspace snapshot이 필요하면 `get_workspace_settings()`
- state/summary는 ContextStateStore 기반 경계
- plot은 PlotStore 기반 경계

즉 production code에서 `get_config()`는 더 이상 새 호출부의 선택지가 아니어야 한다.

이 단계에서는:

- 기존 production caller를 확인하고
- 남아 있다면 Story Bible 전용 API로 교체하고
- 없다면 테스트만 정리한다.

### 5. 테스트 migration 방향

이번 단계 테스트는 API 의미를 보여줘야 한다.

핵심 방향:

- [test_context_manager.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_context_manager.py)
  - Story Bible-only read contract는 새 public API 기준으로 검증
  - `get_config()`는 compatibility alias라는 점을 별도 테스트로 남김

- [test_ui_helpers.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_ui_helpers.py)
  - fake context에 `get_config()`가 남아 있더라도, 새 호출부에 필요 없으면 걷어낸다.

권장 테스트 예시:

- `test_get_story_bible_settings_returns_story_bible_compatibility_view`
- `test_get_config_alias_matches_story_bible_settings`
- `test_default_story_bible_shadow_constant_is_preferred_over_default_config_alias`

핵심은 compatibility와 primary API를 테스트에서 구분하는 것이다.

### 6. 비목표

이번 단계에서 하지 않는 것:

- `get_config()` 제거
- `save_config(...)` 제거
- `DEFAULT_CONFIG` 제거
- `config.json` 파일 제거
- state/plot shadow 경계 변경
- UI 구조 변경
- automation / publishing 흐름 변경

## 완료 기준

다음이 만족되면 이번 단계는 완료다.

1. Story Bible 전용 public read API가 도입된다.
2. `get_config()` / `save_config(...)` / `DEFAULT_CONFIG`는 compatibility alias 성격이 코드에서 더 분명해진다.
3. production code와 주요 테스트가 generic `config`보다 Story Bible 의미를 가진 API/상수를 우선 사용한다.
4. 관련 단위 테스트와 기존 origin 회귀가 통과한다.
