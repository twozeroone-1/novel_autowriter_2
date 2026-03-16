# Story Bible Alias Removal Design

## 배경

`_2`의 Story Bible 경계는 이미 구조적으로 분리돼 있다.

- `StoryBibleStore`가 source of truth다.
- `get_story_bible_settings()`가 primary read API다.
- `save_story_bible_sections(...)`가 primary write API다.
- `DEFAULT_STORY_BIBLE_SETTINGS`가 primary defaults 이름이다.
- `state` / `summary_of_previous`와 `plot_outline` / `plot_version`는 각각 별도 store 경계로 분리됐다.

그 위에 남아 있던 generic alias도 바로 직전 단계까지 정리됐다.

- `DEFAULT_CONFIG`
- `get_config()`
- `save_config(...)`

이제 이 셋은 코드와 테스트에서 `legacy compatibility alias`라는 의미를 명시적으로 가진다.

문제는 여기서 한 단계 더 남아 있다는 점이다.

1. production code 기준으로는 이미 이 alias가 필요하지 않다.
2. 그런데 public surface에는 여전히 남아 있어서, 새 호출부가 다시 generic config 개념을 따라갈 여지가 있다.
3. 테스트도 compatibility 검증 때문에 alias를 계속 끌고 다닌다.

즉 다음 단계의 핵심은 `compatibility 표시`가 아니라 `실제 제거 시점`이다.

## 목표

이번 단계 목표는 네 가지다.

1. `ContextManager`에서 `DEFAULT_CONFIG`, `get_config()`, `save_config(...)`를 제거한다.
2. repo 내부 Story Bible read/write는 오직 primary API만 사용하도록 고정한다.
3. 테스트를 alias 제거 이후 계약에 맞게 다시 정리한다.
4. `config.json` shadow는 유지하되, 더 이상 generic public API surface와 연결되지 않게 만든다.

## 선택지

### 옵션 1. alias 유지

- 지금 상태를 계속 유지한다.

장점:
- 외부 호환성 리스크가 없다.

단점:
- generic config 개념이 코드 표면에 계속 남는다.
- 앞으로도 `왜 primary API가 있는데 alias가 남아 있지?`라는 질문이 반복된다.
- 새 호출부 유입 가능성을 완전히 끊지 못한다.

### 옵션 2. repo 내부 제거, 외부 호환은 별도 shim 없이 종료

- `ContextManager`에서 alias를 바로 제거한다.
- repo 내부 caller와 테스트를 전부 primary API로 옮긴다.
- 추가 deprecation shim은 두지 않는다.

장점:
- 구조가 가장 단순하다.
- 지금 코드베이스 상태와 가장 잘 맞는다.
- generic config 개념을 `ContextManager` public surface에서 완전히 지운다.

단점:
- hidden external caller가 있다면 즉시 깨질 수 있다.

### 옵션 3. shim 파일 또는 별도 compatibility layer 유지

- `ContextManager`에서는 alias를 제거하되, 별도 compatibility helper를 만든다.

장점:
- 외부 호환을 단계적으로 유지할 수 있다.

단점:
- 실제로는 generic alias를 다른 위치로 옮기는 것에 가깝다.
- 현재 repo 내부에 caller가 거의 없는데 과한 대응이다.

이번 단계는 옵션 2를 채택한다.

이유는 명확하다. 현재 검색 기준으로 production UI나 runtime은 이미 이 alias를 쓰지 않고, 남은 사용처는 [test_context_manager.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_context_manager.py)와 [core/context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py) 정의 자체에 집중돼 있다. 즉 지금이 제거 비용이 가장 낮은 시점이다.

## 설계

### 1. `ContextManager` public surface에서 generic alias 제거

[context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)에서 다음 public alias를 제거한다.

- `DEFAULT_CONFIG`
- `get_config()`
- `save_config(...)`

유지되는 Story Bible public contract는 다음 셋이다.

- `DEFAULT_STORY_BIBLE_SETTINGS`
- `get_story_bible_settings()`
- `save_story_bible_sections(...)`

핵심은 “generic config”라는 이름을 더 이상 `ContextManager`의 public API로 제공하지 않는 것이다.

### 2. shadow file은 남기되 private implementation detail로 후퇴

이번 단계는 `config.json` shadow를 없애는 단계가 아니다.

계속 유지되는 것:

- Story Bible shadow write helper
- state shadow write helper
- plot shadow write helper
- legacy fallback read for state/plot where already 존재하는 계약

바뀌는 것:

- 이 shadow는 public generic API의 근거가 아니다.
- public consumer는 shadow 존재 여부를 몰라도 된다.

즉 `config.json`은 여전히 compatibility persistence file이지만, `ContextManager`의 generic facade는 더 이상 아니다.

### 3. 테스트도 primary Story Bible 계약만 검증

[test_context_manager.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_context_manager.py)에서 compatibility-path 테스트를 제거한다.

제거 대상 예시:

- `DEFAULT_CONFIG` alias identity 테스트
- `get_config()` alias equality 테스트
- `save_config(...)` delegation 테스트
- `save_config(...)` 기반 state/plot ignore 테스트

남겨야 하는 핵심은 primary 계약이다.

- `get_story_bible_settings()`가 Story Bible compatibility view를 올바르게 돌려주는가
- `save_story_bible_sections(...)`가 structured store와 shadow를 함께 갱신하는가
- Story Bible write가 state/plot shadow를 덮어쓰지 않는가

즉 테스트는 더 이상 “alias가 primary와 같다”를 보지 않고, 그냥 primary contract 자체를 본다.

### 4. save/write 관련 테스트는 primary API로 재서술

지금 alias 제거에서 가장 큰 변경은 write path 테스트다.

기존 일부 테스트는 `save_config(...)`에 `plot_outline`, `state`, `summary_of_previous` 같은 필드를 섞어서 “무시되는가”를 검증한다. alias를 제거하면 이 시나리오는 계약 자체가 사라진다.

대신 테스트를 이렇게 다시 쓴다.

- `save_story_bible_sections(...)`가 Story Bible 필드만 갱신한다
- 기존 state shadow와 plot shadow는 보존된다
- `get_workspace_settings()`와 각 store는 계속 분리된 값을 보여준다

즉 “무시되는 generic input” 검증이 아니라 “분리된 저장 경계가 서로를 오염시키지 않음” 검증으로 바뀐다.

### 5. hidden caller 리스크는 repo 내부 기준으로 관리

이번 단계는 외부 배포 라이브러리의 semver 호환 문제가 아니라, 현재 프로젝트 내부 구조 정리다.

따라서 판단 기준은 repo 내부다.

- production code가 alias를 쓰지 않으면 제거한다.
- 테스트만 남아 있으면 primary contract 테스트로 옮긴다.
- 외부 문서나 README에 alias가 남아 있으면 그건 별도 후속 정리 대상으로 본다.

즉 이번 단계에서 “혹시 바깥에서 누가 import할지도 모른다”는 가정 때문에 generic alias를 계속 붙잡고 있지는 않는다.

### 6. 비가역적 public surface 축소이므로 문서와 커밋을 분리

이번 단계는 docstring이나 naming 정리보다 한 단계 강하다.

그래서 구현 계획은 두 묶음으로 가는 게 맞다.

1. failing test로 alias 제거 후 계약을 고정
2. minimal code removal + broad regression

커밋도 가능하면 다음처럼 나눈다.

- alias 제거
- primary contract 테스트 정리

이렇게 해야 회귀가 생기면 어느 지점에서 public contract가 바뀌었는지 추적하기 쉽다.

## 비목표

이번 단계에서 하지 않는 것:

- `config.json` shadow 파일 제거
- Story Bible shadow helper 제거
- state/plot shadow 구조 변경
- UI 흐름 변경
- automation / publishing 흐름 변경
- StoryBibleStore 스키마 변경

## 완료 기준

다음이 만족되면 이번 단계는 완료다.

1. [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)에서 `DEFAULT_CONFIG`, `get_config()`, `save_config(...)`가 제거된다.
2. Story Bible public contract는 `DEFAULT_STORY_BIBLE_SETTINGS`, `get_story_bible_settings()`, `save_story_bible_sections(...)`로만 남는다.
3. [test_context_manager.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_context_manager.py)는 alias 대신 primary Story Bible contract만 검증한다.
4. origin 회귀와 syntax verification이 통과한다.
