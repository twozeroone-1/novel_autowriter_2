# Publish Canon Gating Design

## 배경

현재 `_2`는 `CanonExtractor`를 갖고 있고, `Automator` 결과에 `canon_update` 후보를 포함할 수 있다. 하지만 `PublishingRuntime`은 아직 과도기 상태다.

- `result["canon_update"]`나 `job["canon_update"]`가 있으면 CanonStore에 병합한다.
- 둘 다 없으면 `timeline`만 추가하는 fallback을 유지한다.

이 동작은 상위 설계 문서의 Gate 5와 맞지 않는다. Gate 5의 핵심은 다음이다.

- 품질 게이트 통과
- 실제 플랫폼 발행 검증 성공
- 구조화 사실 추출 결과가 스키마 검증 통과

즉, 발행 성공만으로 Canon DB가 바뀌어서는 안 된다.

## 목표

이번 하위 단계의 목표는 두 가지다.

1. 발행 성공 이후에도 구조화 추출이 성공해야만 Canon DB를 갱신하게 만든다.
2. 추출 성공/실패/스킵 상태를 런타임 기록과 snapshot에 남겨 운영자가 사후 분석할 수 있게 한다.

## 선택지

### 옵션 1. Provided candidate only

- `result["canon_update"]` 또는 `job["canon_update"]`만 신뢰
- 후보가 없으면 Canon DB 갱신 생략

장점:
- 비용이 가장 낮다.

단점:
- 수동 발행이나 레거시 publish queue 경로에서는 Canon DB가 거의 갱신되지 않을 수 있다.

### 옵션 2. Provided candidate 우선, 없으면 publish 시점 extractor fallback

- 먼저 `result/job`에 실린 후보를 사용
- 없거나 비어 있으면 source content로 extractor를 한 번 더 호출
- 그래도 실패하면 Canon DB를 건드리지 않음

장점:
- 자동화 경로와 수동 발행 경로를 둘 다 커버한다.
- 구조화 추출 성공이 없는 Canon 갱신을 막을 수 있다.

단점:
- 발행 성공 후 추가 LLM 호출 비용이 생길 수 있다.

### 옵션 3. Artifact-persisted candidate mandatory

- publishable artifact에 구조화 후보를 영속 저장
- publish runtime은 그 저장된 후보만 사용

장점:
- 비용과 재현성이 가장 좋다.

단점:
- episode artifact 구조 변경 범위가 커진다.
- 이번 단계 범위를 넘는다.

이번 단계는 옵션 2를 채택한다.

## 설계

### 1. Canon update resolution

`PublishingRuntime` 내부에 “발행 성공 후 Canon update를 해석하는” 작은 경계를 둔다.

해석 순서:

1. `result["canon_update"]`
2. `job["canon_update"]`
3. extractor fallback on `source_payload["content"]`

어느 경로든 최종 payload는 `normalize_canon_candidate()`를 통과해야 한다.

### 2. Canon gating

다음 조건이 모두 만족될 때만 CanonStore를 갱신한다.

- `overall_status == "done"`
- `episode_id` 존재
- 구조화 candidate가 non-empty

하나라도 빠지면:

- `CanonStore.apply_state_update()` 호출 금지
- Canon snapshot 생성 금지

즉, 기존 `{"timeline": [episode_id]}` fallback은 제거한다.

### 3. Runtime evidence

발행 성공 후 Canon 처리 결과를 명시적으로 기록한다.

추천 shape:

```json
{
  "status": "applied" | "skipped" | "failed",
  "source": "result" | "job" | "extractor" | "none",
  "error": "",
  "candidate": { ... }
}
```

이 payload는 두 군데에 남긴다.

- `runs/<run_id>/canon_update.json`
- publishing history record의 `canon_update`

이렇게 해야 운영자가 “왜 Canon DB가 안 바뀌었는지”를 실행 단위로 확인할 수 있다.

### 4. Event logging

`canon/events.jsonl`에는 여전히 발행 성공 이벤트를 남길 수 있다. 다만 Canon 반영 성공 여부를 함께 적는다.

예:

```json
{
  "kind": "origin_publish_success",
  "episode_id": "ep_021",
  "canon_update_status": "applied",
  "canon_update_source": "extractor"
}
```

이 이벤트는 “발행은 성공했지만 Canon은 미반영” 상황도 분리해서 관측하게 해준다.

## 테스트

필수 테스트는 다음과 같다.

1. provided `canon_update`가 있으면 그것을 반영한다.
2. provided candidate가 없으면 extractor fallback으로 Canon을 반영한다.
3. extractor가 실패하면 Canon DB는 생성/갱신되지 않는다.
4. history와 run snapshot에 `canon_update.status`가 남는다.

## 비목표

이번 단계에서 하지 않는 것:

- episode artifact manifest에 Canon candidate 영속화
- workspace UI에서 Canon DB 직접 편집
- Planner 기반 구조 입력을 extractor에 주입

## 완료 기준

다음이 만족되면 이번 단계는 완료다.

1. `timeline` 단독 fallback이 제거된다.
2. publish success만으로 Canon DB가 바뀌지 않는다.
3. provided candidate 또는 extractor fallback이 성공할 때만 Canon DB가 갱신된다.
4. Canon 처리 결과가 history와 run snapshot에 남는다.
