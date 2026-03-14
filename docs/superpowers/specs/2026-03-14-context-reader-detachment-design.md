# Context Reader Detachment Design

## 배경

지금까지의 단계로 저장 경계는 상당 부분 정리됐다.

- Story Bible은 [story_bible_store.py](/mnt/c/Users/W/novel_autowriter_2/core/story_bible_store.py) 기준으로 관리된다.
- `STATE` / `PREVIOUS SUMMARY`는 전용 저장 메서드로 다뤄진다.
- plot은 [plot_store.py](/mnt/c/Users/W/novel_autowriter_2/core/plot_store.py) 기준으로 분리됐다.
- 일반 config 계약에서는 plot도 이미 분리됐다.

하지만 [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py) 내부의 “읽기 경계”는 아직 절반쯤 레거시다.

- `get_worldview_context()`는 아직 `get_config()`를 경유한다.
- `get_continuity_context()`도 `get_config()`를 경유한다.
- `get_state_context()` 역시 `get_config()`를 경유한다.
- `build_updated_summary_text()`도 이전 summary를 읽기 위해 `get_config()`를 사용한다.

즉 외부 저장 경계는 구조화됐지만, 내부 prompt/context reader는 아직 “합쳐진 legacy snapshot”에 기대는 모양이다. 이 상태로는 `get_config()`가 계속 사실상의 중심 API처럼 남아 있게 된다.

## 목표

이번 단계의 목표는 세 가지다.

1. `ContextManager` 내부의 prompt/context reader가 `get_config()`를 기본 읽기 경로로 사용하지 않게 만든다.
2. Story Bible, state/summary, plot이 각자 전용 읽기 경계를 통해 소비되도록 정리한다.
3. `get_config()`는 즉시 제거하지 않고, 호환 API로만 남긴다.

## 선택지

### 옵션 1. 현 상태 유지

- 저장 경계만 구조화하고, 내부 reader는 계속 `get_config()`를 경유한다.

장점:
- 구현 비용이 가장 낮다.

단점:
- `get_config()`가 계속 중심처럼 남는다.
- 이후 레거시 API 축소가 늦어진다.

### 옵션 2. 내부 reader만 분리하고 `get_config()`는 호환용으로 유지

- Story Bible reader는 `StoryBibleStore`
- state/summary reader는 workspace/state snapshot
- plot reader는 기존 plot API
- `get_config()`는 외부 호환을 위해 남기되, production reader는 더 이상 그것에 기대지 않는다.

장점:
- 범위가 작고 안전하다.
- 다음 단계에서 `get_config()`를 더 명확히 legacy/compatibility API로 밀어낼 수 있다.

단점:
- `get_config()` 자체는 아직 남아 있다.

### 옵션 3. `get_config()` 제거 또는 대규모 rename

- 내부 reader뿐 아니라 외부 테스트와 호출부까지 전면 전환한다.

장점:
- 장기적으로는 가장 깔끔하다.

단점:
- 이번 단계 범위를 넘긴다.
- 불필요하게 많은 테스트와 호출부를 흔든다.

이번 단계는 옵션 2를 채택한다.

## 설계

### 1. Story Bible reader 분리

`get_worldview_context()`와 `get_continuity_context()`는 더 이상 `get_config()`를 경유하지 않는다.

권장 방식:

- Story Bible snapshot 전용 helper 추가
  - 예: `_get_story_bible_prompt_fields()`
- 이 helper는 `StoryBibleStore.load()` 결과를 기준으로 다음을 반환한다.
  - `worldview`
  - `tone_and_manner` 대응값
  - `continuity` 대응값

중요한 점은 `ContextManager.get_config()`의 합쳐진 snapshot을 다시 거치지 않는 것이다.

### 2. state/summary reader 분리

`get_state_context()`와 `build_updated_summary_text()`는 state 전용 snapshot을 사용한다.

권장 방식:

- state snapshot helper 추가
  - 예: `_get_state_snapshot()`
- 이 helper는 전용 저장 경계 기준으로 다음을 반환한다.
  - `state`
  - `summary_of_previous`

이 단계에서 state snapshot은 `get_workspace_settings()`를 재사용해도 되지만, 더 나은 방향은 그 내부에서도 필요한 최소 필드만 읽는 helper를 두는 것이다.

핵심은 “summary를 읽기 위해 전체 config snapshot을 다시 조립하지 않는다”는 점이다.

### 3. `get_workspace_settings()` 역할 정리

이번 단계에서 `get_workspace_settings()`는 유지한다.

다만 역할은 분명히 한다.

- UI snapshot/편집 기본값 공급용
- 필요하면 state reader helper의 기반

반대로 `get_config()`는:

- legacy/compatibility API
- 테스트 또는 구경계 fallback 용도

즉 production reader에서의 우선순위는 `workspace/store helper > get_config()`가 된다.

### 4. public API 유지 범위

이번 단계에서 유지할 public API:

- `get_worldview_context()`
- `get_continuity_context()`
- `get_state_context()`
- `build_updated_summary_text()`
- `get_config()`
- `get_workspace_settings()`

즉 외부 호출부를 바꾸지 않고, 내부 읽기 경계만 재배선한다.

### 5. 테스트 전략

이번 단계의 테스트는 “동작 유지”와 “read path 분리”를 같이 증명해야 한다.

필수 테스트 방향:

- [test_context_manager.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_context_manager.py)
  - `get_worldview_context()`가 `get_config()` 없이도 Story Bible 데이터를 읽는지
  - `get_continuity_context()`가 `get_config()` 없이도 continuity를 읽는지
  - `get_state_context()`가 `get_config()` 없이도 state/summary를 읽는지
  - `build_updated_summary_text()`가 `get_config()` 없이도 기존 summary를 읽는지

권장 테스트 방식:

- `manager.get_config`를 `AssertionError`로 patch
- 전용 저장소/전용 save 메서드로 데이터 세팅
- reader 메서드 호출
- expected text/assertion 확인

이렇게 하면 “reader가 진짜로 `get_config()`를 안 쓴다”를 강하게 검증할 수 있다.

### 6. 비목표

이번 단계에서 하지 않는 것:

- `get_config()` 제거
- UI 호출부 변경
- Story Bible store schema 변경
- state 저장 경계 재설계
- plot reader 변경

## 완료 기준

다음이 만족되면 이번 단계는 완료다.

1. `get_worldview_context()`, `get_continuity_context()`, `get_state_context()`, `build_updated_summary_text()`가 `get_config()`에 기본적으로 의존하지 않는다.
2. 외부 public API와 prompt output behavior는 유지된다.
3. 관련 단위 테스트와 기존 origin 회귀가 통과한다.
