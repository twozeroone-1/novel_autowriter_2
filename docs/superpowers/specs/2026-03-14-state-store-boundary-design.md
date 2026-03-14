# State Store Boundary Design

## 배경

지금까지의 단계로 구조화 저장 경계는 꽤 정리됐다.

- Story Bible은 [story_bible_store.py](/mnt/c/Users/W/novel_autowriter_2/core/story_bible_store.py) 기준으로 관리된다.
- plot은 [plot_store.py](/mnt/c/Users/W/novel_autowriter_2/core/plot_store.py) 기준으로 관리된다.
- prompt reader는 Story Bible과 state snapshot을 직접 읽고, 더 이상 `get_config()`를 기본 reader로 쓰지 않는다.

하지만 `STATE`와 `PREVIOUS SUMMARY`는 아직 [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py) 안에서 `config.json`에 직접 저장된다.

- `save_state(...)`는 아직 `config.json`을 직접 갱신한다.
- `save_previous_summary(...)`도 아직 `config.json`을 직접 갱신한다.
- `_get_state_snapshot()`은 아직 `config.json`을 직접 읽는다.
- `get_workspace_settings()`도 state 계열은 사실상 `config.json`을 기준으로 가져온다.

즉 Story Bible과 plot은 전용 store가 있는데, 실제 회차 운영에 직접 쓰이는 단기 상태는 아직 레거시 config가 본 저장소 역할을 한다. 이 상태로는 `config.json`이 계속 “살아 있는 운영 저장소”로 남게 된다.

## 목표

이번 단계의 목표는 세 가지다.

1. `state`와 `summary_of_previous`를 전용 store로 분리한다.
2. `ContextManager`의 state read/write 경계를 새 store 기준으로 재배선한다.
3. `config.json`은 즉시 제거하지 않고 호환용 shadow로만 남긴다.

## 선택지

### 옵션 1. 현 상태 유지

- `STATE`와 `PREVIOUS SUMMARY`를 계속 `config.json`에 저장한다.

장점:
- 구현 비용이 가장 낮다.

단점:
- `config.json`이 계속 실질적 본 저장소로 남는다.
- Story Bible / plot과 저장 경계 일관성이 깨진다.
- 이후 `get_config()` 축소나 config 제거 단계가 늦어진다.

### 옵션 2. 전용 State Store를 추가하고 legacy shadow를 유지

- 새 `ContextStateStore`를 추가한다.
- `state`와 `summary_of_previous`는 이 store를 기준으로 읽고 쓴다.
- `config.json`에는 호환을 위한 shadow write만 유지한다.

장점:
- 범위가 작고 안전하다.
- 기존 UI와 public API를 거의 건드리지 않는다.
- 다음 단계에서 `config.json`을 더 명확히 compatibility layer로 밀어낼 수 있다.

단점:
- 한동안 store와 shadow가 같이 존재한다.

### 옵션 3. state를 CanonStore에 흡수

- 단기 state와 이전 요약을 CanonStore에 함께 둔다.

장점:
- store 수는 적어진다.

단점:
- 발행 완료 사실과 작업 중 상태가 섞인다.
- CanonStore의 의미가 흐려진다.
- publish gating과 작성 중 context를 같은 저장소에 섞는 건 경계가 나쁘다.

이번 단계는 옵션 2를 채택한다.

## 설계

### 1. `ContextStateStore` 추가

새 파일 [context_state_store.py](/mnt/c/Users/W/novel_autowriter_2/core/context_state_store.py)를 추가한다.

기본 역할:

- `state`
- `summary_of_previous`

두 필드를 정규화해서 읽고 쓰는 것뿐이다.

권장 저장 경로:

- `data/projects/<project>/context_state.json`

권장 기본 구조:

```json
{
  "state": "…",
  "summary_of_previous": "…"
}
```

이 store는 Story Bible이나 plot처럼 “작지만 명확한 단일 책임 저장소”여야 한다.

### 2. `ContextManager` state reader 재배선

[context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)에서 `ContextManager`는 새 store를 주입받는다.

핵심 변경:

- `_get_state_snapshot()`은 `ContextStateStore.load()`를 우선 사용한다.
- store 파일이 아직 없을 때만 legacy `config.json`의 `state` / `summary_of_previous`를 fallback으로 읽는다.

즉 state reader의 기준선은 이제 `config.json`이 아니라 `ContextStateStore`다.

### 3. state writer 재배선

다음 메서드는 새 store를 기준으로 저장한다.

- `save_state(...)`
- `save_previous_summary(...)`

저장 순서는 다음이 적절하다.

1. 현재 `ContextStateStore` payload 로드
2. 대상 필드만 갱신
3. store 저장
4. legacy `config.json` shadow write

이렇게 하면 state 저장도 Story Bible / plot과 비슷한 구조를 갖게 된다.

### 4. `get_workspace_settings()`와 `get_config()` 역할 분리 강화

이번 단계에서 둘 다 유지한다.

하지만 읽기 기준선은 분명히 한다.

`get_workspace_settings()`
- Story Bible은 StoryBibleStore에서 읽는다.
- state/summary는 ContextStateStore에서 읽는다.
- UI snapshot 공급용 API로 유지한다.

`get_config()`
- compatibility API로 유지한다.
- 반환값에는 여전히 `state`와 `summary_of_previous`가 포함될 수 있다.
- 하지만 source of truth는 새 store다.

즉 `get_config()`는 “합쳐진 보기”이고, 본 저장 경계는 아니다.

### 5. lazy migration

이번 단계에서는 별도의 대규모 마이그레이션 명령을 만들지 않는다.

대신 lazy migration으로 충분하다.

- 기존 프로젝트에서 `context_state.json`이 없으면:
  - `_get_state_snapshot()`이 legacy `config.json` 값을 fallback으로 읽는다.
- 이후 사용자가 `save_state(...)` 또는 `save_previous_summary(...)`를 한 번이라도 호출하면:
  - 새 store가 생성된다.
  - 이후 읽기는 새 store를 우선 사용한다.

이 방식이면 기존 프로젝트를 깨지 않고 자연스럽게 전환할 수 있다.

### 6. public API 유지 범위

이번 단계에서 유지할 public API:

- `get_workspace_settings()`
- `get_config()`
- `save_state(...)`
- `save_previous_summary(...)`
- `apply_context_updates(...)`
- `update_summary(...)`

외부 호출부는 그대로 두고, 내부 저장 경계만 바꾼다.

### 7. 테스트 전략

필수 테스트는 세 축이다.

- 새 store의 정규화/round-trip
- `ContextManager`가 새 store를 우선 사용한다는 점
- legacy fallback과 shadow write가 유지된다는 점

권장 테스트:

- [test_context_state_store.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_context_state_store.py)
  - 기본 payload 반환
  - save/load round-trip
  - 누락 필드 정규화

- [test_context_manager.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_context_manager.py)
  - `save_state(...)`가 store와 legacy shadow 둘 다 갱신하는지
  - `save_previous_summary(...)`가 store와 legacy shadow 둘 다 갱신하는지
  - `get_workspace_settings()`가 legacy config보다 ContextStateStore를 우선 읽는지
  - store가 없을 때 legacy state/summary를 fallback으로 읽는지
  - `apply_context_updates(...)`와 `update_summary(...)`가 새 store 경계를 통해 동작하는지

이 단계의 핵심은 “writer도, reader도 이제 state store를 기준으로 돈다”를 테스트로 증명하는 것이다.

### 8. 비목표

이번 단계에서 하지 않는 것:

- `config.json` 제거
- Story Bible shadow 제거
- plot shadow 제거
- UI 레이아웃 변경
- CanonStore schema 변경
- `summary_of_previous`를 더 작은 구조로 쪼개는 일

## 완료 기준

다음이 만족되면 이번 단계는 완료다.

1. `state`와 `summary_of_previous`의 source of truth가 `ContextStateStore`로 바뀐다.
2. `ContextManager`의 state reader/writer가 새 store를 우선 사용한다.
3. 기존 프로젝트는 legacy fallback으로 깨지지 않는다.
4. 관련 단위 테스트와 기존 origin 회귀가 통과한다.
