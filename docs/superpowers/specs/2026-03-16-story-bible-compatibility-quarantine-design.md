# Story Bible Compatibility Quarantine Design

## 배경

`_2`의 Story Bible 경계는 이미 꽤 많이 정리됐다.

- `StoryBibleStore`가 source of truth다.
- `get_story_bible_settings()`가 primary read API다.
- `save_story_bible_sections(...)`가 primary write API다.
- `DEFAULT_STORY_BIBLE_SETTINGS`가 primary defaults 이름이다.
- `state` / `summary_of_previous`와 `plot_outline` / `plot_version`는 각각 전용 store로 분리됐다.

즉 실사용 기준으로는 이미 `generic config` 개념이 사실상 무너졌다.

하지만 compatibility alias는 아직 남아 있다.

- `DEFAULT_CONFIG`
- `get_config()`
- `save_config(...)`

이 셋은 지금도 동작은 맞지만, 두 가지 문제가 남아 있다.

1. 이름만 보면 여전히 “일반 프로젝트 설정 API”처럼 읽힌다.
2. 테스트와 코드 구조를 모르면, 새 호출부가 이 alias를 primary API로 오해할 수 있다.

이제 필요한 건 큰 기능 변경이 아니라, 이 alias들을 명시적으로 `legacy compatibility surface`로 격리하는 일이다.

## 목표

이번 단계 목표는 네 가지다.

1. `DEFAULT_CONFIG`, `get_config()`, `save_config(...)`를 primary API가 아니라 compatibility alias로 더 분명히 표시한다.
2. primary 경로와 compatibility 경로를 테스트에서 명확히 분리한다.
3. 새 코드가 generic alias를 따라가게 만드는 흔적을 더 줄인다.
4. 다음 단계에서 alias 제거 여부를 판단하기 쉬운 상태를 만든다.

## 선택지

### 옵션 1. 현 상태 유지

- alias는 남겨 두되 추가 정리는 하지 않는다.

장점:
- 구현 비용이 없다.

단점:
- 지금 코드만 읽으면 alias와 primary API의 위계가 충분히 드러나지 않는다.
- 다음 단계에서 또 “이 alias를 어디까지 지원해야 하나”를 다시 해석해야 한다.

### 옵션 2. compatibility quarantine

- alias는 유지한다.
- 대신 코드 구조, 주석, 테스트 분류에서 `legacy compatibility only`라는 의미를 분명히 한다.

장점:
- 범위가 작고 안전하다.
- 동작 변경 없이 유지보수 의미를 선명하게 만든다.
- alias 제거를 서두르지 않으면서도 새 호출부 유입을 막기 좋다.

단점:
- 기능 변화가 거의 없어서 겉보기 진척은 작다.

### 옵션 3. alias 즉시 제거

- `DEFAULT_CONFIG`, `get_config()`, `save_config(...)`를 바로 없앤다.

장점:
- 장기적으로 가장 깔끔하다.

단점:
- 아직 hidden caller나 테스트 보정 범위를 한 번 더 검증해야 한다.
- 이번 단계로는 리스크 대비 이득이 크지 않다.

이번 단계는 옵션 2를 채택한다.

## 설계

### 1. alias를 code surface에서 명시적으로 격리

[context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py) 안에서 다음을 더 분명히 한다.

- `DEFAULT_STORY_BIBLE_SETTINGS`는 primary defaults
- `DEFAULT_CONFIG`는 compatibility alias
- `get_story_bible_settings()`는 primary read API
- `get_config()`는 compatibility alias
- `save_story_bible_sections(...)`는 primary write API
- `save_config(...)`는 compatibility alias

핵심은 제거가 아니라 `public contract의 위계`를 코드에서 바로 읽히게 만드는 것이다.

예시 방향:

- alias 정의 바로 위/옆에 compatibility 주석 추가
- 가능하면 primary API와 alias API를 코드상으로 연속 배치
- 새 기본값 참조는 계속 primary 이름을 사용

### 2. 테스트를 primary-path와 compatibility-path로 분리

지금 [test_context_manager.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_context_manager.py)는 많이 정리됐지만, alias 테스트와 primary API 테스트가 파일 안에 섞여 있다.

이번 단계에서는 테스트 의미를 더 명확히 나눈다.

- primary-path 테스트:
  - `get_story_bible_settings()`
  - `save_story_bible_sections(...)`
  - `DEFAULT_STORY_BIBLE_SETTINGS`

- compatibility-path 테스트:
  - `get_config()`가 primary reader와 같은 결과를 돌려주는지
  - `save_config(...)`가 primary write path로 위임되는지
  - `DEFAULT_CONFIG`가 primary defaults alias인지

핵심은 alias 테스트를 남기되, 파일 구조상 “예외 경로”라는 사실이 보이게 만드는 것이다.

### 3. generic naming 흔적은 더 이상 primary 예시로 쓰지 않음

지금 이후 단계에서 새 테스트나 helper를 추가할 때:

- Story Bible payload 예시는 `DEFAULT_STORY_BIBLE_SETTINGS`
- Story Bible reader 예시는 `get_story_bible_settings()`
- Story Bible writer 예시는 `save_story_bible_sections(...)`

를 기준으로 삼는다.

즉 `DEFAULT_CONFIG`나 `get_config()`는 compatibility 검증이 아닌 이상 예시 코드에 쓰지 않는다.

이 원칙은 실제 production behavior보다 `코드 독해 방향`을 정리하는 데 중요하다.

### 4. 이번 단계는 behavior change를 만들지 않음

이번 단계는 동작 변경이 목적이 아니다.

유지해야 하는 것:

- `get_config()`는 계속 동작해야 한다.
- `save_config(...)`는 계속 동작해야 한다.
- `DEFAULT_CONFIG`도 계속 import 가능해야 한다.

바뀌는 것은:

- 코드가 이 셋을 primary API처럼 소개하지 않는다.
- 테스트도 primary path와 compatibility path를 구분해서 설명한다.

### 5. 다음 단계 판단 기준도 함께 남김

이번 quarantine 이후에는 다음 질문에 답하기 쉬워져야 한다.

- production caller가 실제로 alias를 쓰는가
- alias 테스트는 몇 개만 남기면 되는가
- `DEFAULT_CONFIG` 제거가 실제 가치가 있는가

즉 이번 단계는 alias 제거를 하지 않지만, 제거 판단을 위한 관측 상태를 만드는 단계다.

## 비목표

이번 단계에서 하지 않는 것:

- `DEFAULT_CONFIG` 제거
- `get_config()` 제거
- `save_config(...)` 제거
- `config.json` shadow 구조 변경
- state/plot store 경계 변경
- UI 동작 변경
- automation / publishing 흐름 변경

## 완료 기준

다음이 만족되면 이번 단계는 완료다.

1. [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)에서 primary Story Bible API와 compatibility alias의 위계가 더 명확해진다.
2. [test_context_manager.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_context_manager.py)에서 primary-path와 compatibility-path 테스트가 분리되어 읽힌다.
3. 새 기본 예시와 기본값 참조는 primary Story Bible 이름을 사용한다.
4. 관련 테스트와 origin 회귀는 그대로 통과한다.
