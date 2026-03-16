# Publish Control Plane v1 Design

## 배경

현재 `_2`는 [story_bible_store.py](/mnt/c/Users/W/novel_autowriter_2/core/story_bible_store.py), [canon_store.py](/mnt/c/Users/W/novel_autowriter_2/core/canon_store.py), [episode_artifact_store.py](/mnt/c/Users/W/novel_autowriter_2/core/episode_artifact_store.py), [run_snapshot_store.py](/mnt/c/Users/W/novel_autowriter_2/core/run_snapshot_store.py)를 통해 저장 구조와 Canon gating 기초를 이미 갖췄다. 또 [publishing_runtime.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_runtime.py), [publishing_executor.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_executor.py), [publishing_store.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_store.py)로 외부 발행 런타임의 골격도 있다.

문제는 이 골격이 상위 설계 문서인 [완전 자동 웹소설 연재 시스템 설계](/mnt/c/Users/W/novel_autowriter_1/docs/superpowers/specs/2026-03-14-fully-automated-web-novel-serialization-design.md)의 핵심 v1 기능과 아직 정확히 맞물리지 않는다는 점이다.

현재 상태의 한계는 명확하다.

- [publishing_runtime.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_runtime.py)가 스케줄 판정, 품질 게이트, 업로드 결과 해석, 사건 대응, Canon 반영, snapshot/history 기록을 모두 안고 있다.
- 품질 게이트는 [origin_quality.py](/mnt/c/Users/W/novel_autowriter_2/core/origin_quality.py)의 단순 코드 검사 수준에 머물러 있고, 설계 문서가 요구한 `publishable`, `retry_possible`, `hard_fail` 표준 상태가 없다.
- 발행 정책은 [automation_scheduler.py](/mnt/c/Users/W/novel_autowriter_2/core/automation_scheduler.py)의 단순 schedule due 판정에 크게 의존하며, 설계 문서의 `run_now`, `delay`, `cooldown`, `stop` 계층과 거리가 있다.
- 사건 대응은 사실상 `paused` 위주로만 표현되고, 설계 문서가 요구한 `cooldown`, `blocked`, `quality_incident`, `platform_incident`, `data_integrity_incident` 경계가 없다.

즉 지금 필요한 것은 “코드를 예쁘게 정리하는 것”이 아니라, 설계 문서의 v1 필수 기능을 채우기 위해 `Publish Control Plane`을 먼저 실체화하는 것이다.

## 목표

이번 단계 목표는 다섯 가지다.

1. [publishing_runtime.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_runtime.py)를 얇은 coordinator로 축소한다.
2. 설계 문서의 `Quality Gate Orchestrator`, `Release Policy Engine`, `Incident Monitor`, `Canon gating`에 대응하는 작은 모듈 경계를 만든다.
3. 외부 업로드 동작은 유지하되, 발행 가능 판정과 중단 사유를 코드 수준에서 명확히 표현한다.
4. 이번 단계 구현은 `v1 필수 기능`에 직접 필요한 것만 포함하고, 마케팅과 locale 확장은 후속 단계로 남긴다.
5. 이후 문피아/노벨피아 어댑터 고도화, 마케팅, 번역 확장이 들어와도 `PublishingRuntime`이 더 커지지 않게 만든다.

## 선택지

### 옵션 1. 업로드 기능 우선

- 플랫폼 client와 업로드 재조회 검증을 먼저 더 완성한다.

장점:
- 눈에 보이는 외부 기능이 빨리 늘어난다.

단점:
- 설계 문서의 핵심인 `나쁜 회차를 막는 운영 시스템`보다 `업로드 기술`에 먼저 투자하게 된다.
- 품질 판정과 중단 정책이 약한 상태에서 외부 자동화만 강화돼 리스크가 커진다.

### 옵션 2. Publish Control Plane v1 우선

- `Quality Gate`, `Policy`, `Incident`, `Canon finalize`를 먼저 분리한다.
- 업로드 executor는 크게 건드리지 않는다.

장점:
- 상위 설계 문서의 v1 핵심과 가장 직접적으로 연결된다.
- 이후 업로드/마케팅/번역을 얹을 때 구조가 버틴다.
- 지금 코드가 난잡해진 가장 큰 원인인 `runtime 한 파일 과밀`을 줄일 수 있다.

단점:
- 당장 체감되는 UI 변화보다 내부 운영 경계 작업이 많다.

### 옵션 3. 엔드투엔드 반쪽 완성

- 업로드, 게이트, 정책, incident를 조금씩 다 손대서 “대충 다 되는 상태”를 먼저 만든다.

장점:
- 겉으로는 진도가 빨라 보일 수 있다.

단점:
- 현재 `_2`가 복잡해진 패턴을 반복할 가능성이 가장 크다.
- 나중에 다시 정리해야 할 코드가 크게 늘어난다.

이번 단계는 옵션 2를 채택한다.

## 설계

### 1. 이번 단계의 구현 기준은 `기능 우선, 정리는 그 기능을 위한 범위만`

이번 단계는 cleanup-first가 아니다.

기준은 명확하다.

- 먼저 [완전 자동 웹소설 연재 시스템 설계](/mnt/c/Users/W/novel_autowriter_1/docs/superpowers/specs/2026-03-14-fully-automated-web-novel-serialization-design.md)의 v1 필수 기능을 채운다.
- 코드 정리는 그 기능을 넣기 위해 필요한 경계 정리까지만 한다.
- 마케팅, locale, 전면 UI 정리 같은 후순위 작업은 이번 범위에 넣지 않는다.

즉 “코드가 지저분하니 다 뜯어고친다”가 아니라, “v1 운영 제어 평면을 넣기 위해 지금 가장 막히는 파일만 분해한다”가 원칙이다.

### 2. `PublishingRuntime`은 오케스트레이터만 남긴다

[publishing_runtime.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_runtime.py)의 목표 역할은 다음 순서를 조립하는 것뿐이다.

1. 실행 가능성 판정
2. 소스 로드
3. 품질 게이트
4. executor 호출
5. incident 요약
6. Canon finalize
7. snapshot/history/runtime 저장

즉 `PublishingRuntime.tick(...)`은 더 이상 세부 판정 로직을 직접 품지 않는다. 판단은 모두 전용 helper/module이 하고, runtime은 그 결과를 저장소와 snapshot에 반영하는 coordinator가 된다.

### 3. `publishing_policy.py`를 추가한다

새 모듈 [publishing_policy.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_policy.py)는 “이번 tick에서 무엇을 할 수 있는가”만 판단한다.

역할:

- `config.enabled` 확인
- 현재 runtime status 확인
- schedule due 판정
- `pending`/`partial_failed` job 선택
- 실행 불가 사유를 표준화해서 반환

출력 예시:

```python
{
    "action": "run_now" | "skip",
    "reason": "disabled" | "paused" | "running" | "not_due" | "no_job",
    "job": {...} | None,
}
```

이번 단계에서는 설계 문서의 거대한 `Release Policy Engine`을 한 번에 다 구현하지 않는다. 대신 그 엔진이 들어갈 자리를 먼저 코드에 만든다. 현재 [automation_scheduler.py](/mnt/c/Users/W/novel_autowriter_2/core/automation_scheduler.py)의 단순 시간 판정은 내부 구현으로 재사용할 수 있다.

### 4. `publishing_quality.py`를 추가한다

새 모듈 [publishing_quality.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_quality.py)는 Gate 0/1에 해당하는 저비용 품질 판정을 담당한다.

역할:

- source payload의 제목/본문 정합성 확인
- blocked marker, 최소 분량, 반복 문장, 제목 회차 번호 등 코드 기반 검사 실행
- 결과를 설계 문서 용어에 맞춰 표준화

출력 예시:

```python
{
    "status": "publishable" | "retry_possible" | "hard_fail",
    "errors": [...],
    "signals": {...},
}
```

현재 [origin_quality.py](/mnt/c/Users/W/novel_autowriter_2/core/origin_quality.py)는 내부 rule engine으로 유지하되, `PublishingRuntime`이 직접 raw shape를 해석하지 않게 만든다.

이번 단계에서는 Gate 2 구조 검사와 Gate 3 비평 모델은 구현하지 않는다. 다만 결과 상태 이름은 그 후속 단계를 수용할 수 있게 맞춰둔다.

### 5. `publishing_incidents.py`를 추가한다

새 모듈 [publishing_incidents.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_incidents.py)는 platform result를 운영 상태로 번역한다.

역할:

- platform별 결과를 읽어 `done`, `partial_failed`, `failed` 계산
- `requires_user_action`, retryable 실패, permanent 실패를 분류
- next runtime status를 계산
- incident type과 last error를 결정

이번 단계 저장 상태는 다음 다섯 개만 도입한다.

- `idle`
- `running`
- `cooldown`
- `paused`
- `blocked`

`scheduled`는 저장 상태가 아니라 policy가 계산하는 표시 상태로 둔다. `stopped`는 작품 단위 장기 중단 정책까지 들어갈 때의 후속 상태로 남긴다.

incident type은 최소한 다음을 구분한다.

- `quality_incident`
- `platform_incident`
- `credential_incident`
- `data_integrity_incident`

이렇게 해야 설계 문서가 요구한 “왜 멈췄는지 알 수 있는 운영 상태”가 생긴다.

### 6. `publishing_canon.py`를 추가한다

새 모듈 [publishing_canon.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_canon.py)는 발행 성공 후 Canon 반영만 담당한다.

역할:

- `result -> job -> artifact -> extractor fallback` 순으로 canon candidate 해석
- 성공 조건일 때만 Canon event append와 snapshot write 수행
- 실패/스킵/빈 후보 상태를 명시적 report로 반환

즉 이 모듈은 상위 설계 문서의 Gate 5를 코드로 고정하는 자리다. 발행이 성공해도 구조화 candidate가 비어 있거나 invalid면 Canon은 갱신되지 않는다.

### 7. executor와 platform client는 이번 단계에서 크게 안 건드린다

[publishing_executor.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_executor.py)와 플랫폼 client는 이번 단계의 주 공격 대상이 아니다.

이유:

- 현재 우선순위는 `어떻게 업로드하나`보다 `어떤 회차를 왜 멈추고 왜 통과시키나`다.
- executor를 크게 건드리면 브라우저 자동화와 운영 제어 평면 정리가 한 번에 섞인다.
- 그러면 설계 문서의 v1 핵심을 먼저 채우겠다는 원칙이 무너진다.

따라서 이번 단계는 executor interface를 유지하고, control plane이 executor 결과를 더 명확히 해석하게 만든다.

### 8. 테스트는 runtime에서 세부 판정을 걷어내는 방향으로 재편한다

새 테스트 축은 이렇게 나눈다.

- [test_publishing_policy.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_publishing_policy.py)
  - 실행 가능성 판정
- [test_publishing_quality.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_publishing_quality.py)
  - Gate 0/1 상태 표준화
- [test_publishing_incidents.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_publishing_incidents.py)
  - incident 분류와 next runtime status 계산
- [test_publishing_canon.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_publishing_canon.py)
  - candidate 해석 우선순위와 Canon finalize 규칙
- [test_publishing_runtime.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_publishing_runtime.py)
  - coordinator 회귀만 유지

이렇게 해야 지금 [publishing_runtime.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_runtime.py) 하나에 세부 로직 검증이 몰려 있는 상태를 풀 수 있다.

## 비목표

이번 단계에서 하지 않는 것:

- Marketing Packager 구현
- locale/translation 파이프라인 구현
- 문피아/노벨피아 client 전면 재작성
- Planner/Reviewer 교체
- Gate 2 구조 검사 완성
- Gate 3 비평 모델 완성
- 하루 2연참 같은 고급 policy 최적화
- 작품 단위 장기 `stopped` 정책 완성

## 완료 기준

다음이 만족되면 이번 단계 스펙은 구현 완료로 본다.

1. [publishing_runtime.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_runtime.py)는 coordinator 역할만 남고, 세부 판정 로직이 helper/module로 빠진다.
2. `Quality Gate`, `Policy`, `Incident`, `Canon finalize`에 대응하는 모듈이 각각 생긴다.
3. 발행 전 품질 판정 결과가 최소한 `publishable`, `retry_possible`, `hard_fail` 상태로 표준화된다.
4. runtime status가 `idle`, `running`, `cooldown`, `paused`, `blocked`까지는 코드와 기록에 반영된다.
5. Canon 반영은 계속 `발행 성공 + candidate 유효` 조건에서만 일어난다.
6. 새 단위 테스트 축과 기존 publishing 회귀가 함께 통과한다.
