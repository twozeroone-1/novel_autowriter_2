# Canon Extractor Integration Design

## 배경

현재 `_2`의 원문 파이프라인은 `Story Bible`, `CanonStore`, `ReleasePolicyStore`, `EpisodeArtifactStore`, `RunSnapshotStore`까지는 분리됐다. 하지만 구조화 사실 추출은 아직 비어 있다.

- `AutomationRuntime`은 `canon_update` 후보가 있으면 실행 기록에 남길 수 있다.
- `PublishingRuntime`은 발행 성공 시 `timeline`만 기계적으로 늘린다.
- `Automator`와 `Generator`는 아직 구조화 Canon 후보를 만들지 않는다.

이 상태에서는 “발행 성공 후 구조화 Canon 갱신”이라는 상위 설계 목표에 필요한 중간 산출물이 없다.

## 목표

이번 하위 설계의 목표는 세 가지다.

1. 최종 수정본에서 구조화 `canon_update` 후보를 생성한다.
2. 자동화/반자동 파이프라인 결과에 그 후보를 실어 디버깅 가능하게 만든다.
3. 발행 성공 경로가 그 후보를 받을 수 있는 인터페이스를 갖추게 한다.

이번 단계에서는 플랫폼 업로드 전후의 완전한 Canon 반영 정책까지 끝내지 않는다. 핵심은 “후보 생성”과 “후보 소비 경계”를 맞추는 것이다.

## 선택지

### 옵션 1. `Automator` 내부 즉석 dict 조립

- 장점: 가장 빠르다.
- 단점: 추출 규칙이 런타임에 묻혀 재사용이 안 된다.
- 단점: 테스트가 `Automator`에 과도하게 결합된다.

### 옵션 2. 공유 `CanonExtractor` 서비스

- 장점: 후보 생성 규칙이 한 곳에 모인다.
- 장점: `Generator/Automator`와 `PublishingRuntime`이 같은 정규화 규칙을 공유할 수 있다.
- 장점: 이후 LLM 기반 추출에서 규칙/스키마를 바꿔도 변경 범위가 작다.
- 단점: 파일 하나가 더 생긴다.

### 옵션 3. 발행 시점 추출 전용

- 장점: Canon DB 갱신과 가장 가깝다.
- 단점: 자동화 기록에 후보가 남지 않아 원인 추적이 나빠진다.
- 단점: 반자동/생성 단계와 발행 단계가 서로 다른 추출 규칙을 쓰게 될 가능성이 높다.

이번 단계는 옵션 2를 채택한다.

## 설계

### 1. `core/canon_extractor.py`

새 모듈을 둔다.

역할:
- 최종 회차 본문에서 구조화 사실 후보를 뽑는다.
- 후보를 `CanonStore` 스키마와 같은 모양으로 정규화한다.
- 비어 있거나 파싱 실패한 결과를 명시적으로 구분한다.

출력 shape:

```json
{
  "people": {},
  "resources": {},
  "hooks": [],
  "timeline": []
}
```

초기 단계에서는 현재 장 본문만 입력으로 사용한다. 장기적으로는 `Canon current state`와 `Planner output`을 추가해도 되지만, 이번 범위에서는 넣지 않는다.

추출은 LLM JSON 응답 기반으로 한다. 이미 코드베이스에 있는 `generate_text()`와 `_extract_first_json_value()`를 재사용한다.

### 2. `Generator` 경계

`Generator`에는 본문에서 Canon 후보를 만드는 얇은 래퍼만 둔다.

- `build_canon_update_candidate(chapter_content: str) -> dict`

이 메서드는 추출 세부 규칙을 직접 가지지 않고 `CanonExtractor`를 호출한다. `Generator`가 직접 JSON 파싱 로직을 들고 있으면 이후 변경이 커지기 때문이다.

### 3. `Automator` 결과 확장

`Automator.run_single_cycle()`는 기존의 `new_state`, `new_summary`와 별도로 다음 필드를 결과에 포함한다.

- `canon_update`
- `canon_update_error`

추출 실패는 파이프라인 전체 실패로 올리지 않는다. 이유는 이번 단계의 Canon 추출은 품질 관측 데이터이자 후속 반영 준비 단계이기 때문이다.

즉:
- 초안 생성/검수/수정본 저장은 계속 성공 처리
- Canon 추출만 실패하면 결과에 에러 문자열만 남김

### 4. `PublishingRuntime` 소비 경계

`PublishingRuntime`은 발행 성공 시 `job` 또는 executor 결과에서 `canon_update`가 넘어오면 그것을 우선 사용한다.

이번 단계의 정책:
- `canon_update`가 유효하면 `CanonStore.apply_state_update()`에 전달한다.
- `timeline`에는 해당 `episode_id`를 보강한다.
- `canon_update`가 없으면 기존의 `timeline` 단독 업데이트를 유지한다.

이건 과도기적 호환 정책이다. 상위 설계의 최종 상태는 “구조화 추출 성공 시에만 Canon DB 갱신”이지만, 지금은 후보 전달 경계를 먼저 안정화하는 데 집중한다.

### 5. 테스트 전략

필수 테스트는 세 묶음이다.

- `CanonExtractor`
  - JSON 응답 파싱 성공
  - 잘못된 응답 시 예외 또는 빈 후보 처리
  - 부분 payload 정규화
- `Automator`
  - 성공 시 `canon_update` 포함
  - 추출 실패 시 전체 파이프라인은 유지되고 `canon_update_error`만 남음
- `PublishingRuntime`
  - 성공한 발행 결과에 `canon_update`가 있으면 CanonStore에 반영
  - 후보가 없으면 기존 timeline fallback 유지

## 비목표

이번 단계에서 하지 않는 것:

- Canon 반영을 발행 성공 + 구조화 추출 성공으로 완전히 강제하는 정책 전환
- Planner 기반 구조 입력 추가
- Workspace UI의 Canon 직접 편집 화면
- 해외 로케일 파이프라인 연동

## 완료 기준

다음이 만족되면 이번 단계는 끝난다.

1. `Automator` 결과에 구조화 `canon_update` 후보가 실린다.
2. 자동화 기록이 실제 후보 payload를 담는다.
3. `PublishingRuntime`이 후보 payload를 받아 CanonStore에 반영할 수 있다.
4. 관련 단위 테스트와 원문 파이프라인 회귀 테스트가 통과한다.
