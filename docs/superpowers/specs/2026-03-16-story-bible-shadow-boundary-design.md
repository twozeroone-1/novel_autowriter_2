# Story Bible Shadow Boundary Design

## 배경

`_2`의 `ContextManager`는 큰 흐름에서 이미 많이 정리됐다.

- `state` / `summary_of_previous`는 [context_state_store.py](/mnt/c/Users/W/novel_autowriter_2/core/context_state_store.py) 기준으로 분리됐다.
- `plot_outline` / `plot_version`는 [plot_store.py](/mnt/c/Users/W/novel_autowriter_2/core/plot_store.py) 기준으로 분리됐다.
- production UI는 대부분 `get_workspace_settings()`와 전용 save 경계를 기준으로 동작한다.
- `get_config()`는 이제 Story Bible-only compatibility read API로 축소됐다.

하지만 [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py) 내부를 보면, 아직도 `config.json` 호환 계층이 “일반 config 시스템”처럼 남아 있다.

대표적으로:

- `DEFAULT_CONFIG`
- `_normalize_config(...)`
- `_load_normalized_config()`
- `_merge_story_bible_into_config(...)`
- `_write_legacy_config(...)`

이 이름과 구조는 마치 `config.json`이 여전히 프로젝트 설정의 중심 저장소인 것처럼 보이게 만든다. 실제로는 아니다. 지금 `config.json`은:

- Story Bible shadow
- state shadow
- plot shadow

를 담는 호환 파일일 뿐이다.

즉 다음 문제는 기능 오류보다 `코드 경계의 의미 왜곡`이다.

## 목표

이번 단계 목표는 네 가지다.

1. `context.py` 내부에서 “일반 config”라는 표현을 더 줄이고 `Story Bible shadow` 호환 계층으로 의미를 분명히 한다.
2. Story Bible 관련 helper를 `config.json` generic helper가 아니라 `legacy shadow helper`로 재배치한다.
3. `save_story_bible_sections(...)`와 `save_config(...)`가 같은 Story Bible shadow write 경계를 공유하게 한다.
4. 이후 단계에서 `get_config()` / `save_config()` 제거 또는 축소를 더 쉽게 만들 준비를 한다.

## 선택지

### 옵션 1. 현 상태 유지

- 지금 구조를 그대로 둔다.

장점:
- 구현 비용이 없다.

단점:
- 코드상 의미가 흐리다.
- `config.json`이 아직도 “주 설정 저장소”처럼 읽힌다.
- 다음 단계에서 `get_config()` / `save_config()`를 줄일 때 경계가 다시 헷갈린다.

### 옵션 2. Story Bible shadow boundary로 내부 helper를 명시적으로 재구성

- generic `config` helper를 Story Bible shadow 중심 helper로 바꾼다.
- public API는 대부분 유지한다.

장점:
- 범위가 작고 안전하다.
- production 동작을 거의 안 건드리면서 내부 책임이 선명해진다.
- 다음에 legacy config API를 더 줄이기 쉬워진다.

단점:
- 이름 변경과 테스트 정리가 조금 필요하다.

### 옵션 3. `get_config()` / `save_config()`를 바로 제거

- compatibility API 자체를 큰 폭으로 걷어낸다.

장점:
- 장기적으로 가장 깔끔하다.

단점:
- 지금은 범위가 크다.
- 테스트와 fallback 경계를 한 번에 많이 건드려야 한다.
- hidden compatibility caller가 있으면 리스크가 크다.

이번 단계는 옵션 2를 채택한다.

## 설계

### 1. “config” helper를 “Story Bible shadow” helper로 재명명

[context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py) 안의 generic helper 이름은 실제 책임에 맞게 바꾼다.

예시 방향:

- `DEFAULT_CONFIG`
  - 유지하더라도 Story Bible compatibility defaults라는 의미를 문서화한다.
  - 가능하면 후속 이름은 `DEFAULT_STORY_BIBLE_SHADOW`처럼 더 구체적인 방향을 고려한다.

- `_normalize_config(...)`
  - Story Bible shadow payload 정규화 helper로 바꾼다.

- `_load_normalized_config()`
  - Story Bible shadow read helper로 바꾼다.

- `_write_legacy_config(...)`
  - Story Bible shadow write helper로 바꾼다.

핵심은 “무엇이 남아 있나”보다 “이게 무엇을 위한 계층인가”를 코드 이름에 반영하는 것이다.

### 2. Story Bible shadow read/write를 하나의 compatibility boundary로 묶기

현재는 Story Bible 관련 public API들이 다음처럼 흩어져 있다.

- `get_config()`는 Story Bible shadow read + structured store merge
- `save_config(...)`는 Story Bible shadow write + structured store save
- `save_story_bible_sections(...)`는 Story Bible structured save + legacy shadow write

이번 단계에서는 내부 경계를 다음처럼 통일한다.

- `StoryBibleStore`가 source of truth
- `config.json`의 Story Bible 필드는 shadow copy
- public Story Bible mutator는 모두 같은 shadow write helper를 사용

즉 `save_story_bible_sections(...)`와 `save_config(...)`가 각각 제멋대로 raw/normalized payload를 만지는 구조를 줄인다.

### 3. `get_config()`는 compatibility view라는 사실을 더 명확히 한다

지금 `get_config()`는 production에서 거의 쓰지 않는다. 그럼에도 이름상으로는 여전히 “현재 프로젝트 설정 전체”처럼 보인다.

이번 단계에서는 제거하지는 않되, 구현과 테스트에서 다음 규칙을 강화한다.

- `get_config()`는 Story Bible compatibility view
- workspace snapshot은 여전히 `get_workspace_settings()`
- state/summary/plot은 `get_config()` 계약에 포함되지 않음

즉 `get_config()`는 “과거 호출부를 위해 남겨 둔 Story Bible view”라는 성격이 더 분명해져야 한다.

### 4. `config.json` 초기화와 shadow write에서 불필요한 일반화 제거

현재 `config.json` 관련 helper는 “모든 필드를 다루는 프로젝트 메타 파일”처럼 보일 수 있다.

이번 단계에서는 최소한 다음 원칙을 코드에 반영한다.

- 기본 생성 시에는 Story Bible shadow 기본값만 가진다.
- state shadow는 `save_state(...)` / `save_previous_summary(...)`가 필요할 때만 생긴다.
- plot shadow는 `save_plot_outline(...)`가 필요할 때만 생긴다.

즉 `config.json`은 “빈 general config”가 아니라 “필요한 호환 shadow들이 붙는 파일”이라는 구조를 유지한다.

### 5. 테스트도 compatibility 의미를 드러내게 정리

테스트는 지금도 많이 좋아졌지만, 다음 메시지를 더 분명히 보여야 한다.

- `get_config()`는 Story Bible만 본다.
- `get_workspace_settings()`는 workspace snapshot이다.
- `save_story_bible_sections(...)`와 `save_config(...)`는 Story Bible shadow를 같은 경계로 갱신한다.
- state/plot shadow는 별도 API가 생길 때만 `config.json`에 추가된다.

권장 테스트 방향:

- [test_context_manager.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_context_manager.py)
  - Story Bible shadow helper 경계가 같은 결과를 만드는지
  - 새 `config.json`이 state/summary 없이 시작하는지
  - `save_story_bible_sections(...)`가 state shadow를 덮지 않는지

이번 단계는 테스트 의미를 바꾸는 것이지, 새로운 사용자 기능을 추가하는 단계는 아니다.

### 6. production 호출부는 유지

이번 단계에서 production 호출부를 크게 바꾸지는 않는다.

이유:

- UI는 이미 workspace snapshot과 전용 save 경계를 기준으로 움직인다.
- prompt reader도 structured store와 snapshot helper 기준으로 정리돼 있다.
- 지금 필요한 건 public behavior 변경이 아니라 `context.py` 내부 경계 명확화다.

즉 주 변경 파일은 대부분:

- [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)
- [test_context_manager.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_context_manager.py)

에 집중된다.

## 비목표

이번 단계에서 하지 않는 것:

- `get_config()` 제거
- `save_config()` 제거
- `config.json` 파일 제거
- state shadow 제거
- plot shadow 제거
- UI 탭 구조 변경
- automation / publishing 흐름 변경

## 완료 기준

다음이 만족되면 이번 단계는 완료다.

1. `context.py` 내부에서 Story Bible 호환 계층이 generic config보다 명확한 이름과 책임을 가진다.
2. `save_story_bible_sections(...)`와 `save_config(...)`가 같은 Story Bible shadow write boundary를 공유한다.
3. `get_config()`가 Story Bible compatibility view라는 사실이 코드와 테스트에서 더 분명해진다.
4. 관련 단위 테스트와 기존 origin 회귀가 통과한다.
