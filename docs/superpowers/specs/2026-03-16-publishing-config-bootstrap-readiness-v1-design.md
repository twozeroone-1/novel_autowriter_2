# Publishing Config Bootstrap And Readiness V1 Design

## Purpose

`1~4단계` 기능은 v1 기준으로 거의 닫혔지만, 실제 smoke를 돌리려면 프로젝트별 발행 설정이 먼저 준비되어야 한다. 현재는 `PublishingStore.load_config()`가 메모리 기본값을 돌려주기 때문에 화면은 동작하지만, 프로젝트 디렉터리에는 실제 `publishing/config.json`이 없을 수 있다. 이 상태에서는:

- 운영자가 어떤 값을 파일로 채워야 하는지 분명하지 않고
- UI readiness와 smoke 차단 사유가 조금씩 다르게 계산되며
- 첫 실운영 준비 과정이 불필요하게 흐려진다

이번 slice의 목표는 다음 두 가지다.

1. 프로젝트에 `publishing/config.json` 기준 파일을 자동 bootstrap 한다.
2. UI와 smoke가 같은 readiness validator를 공유하도록 정리한다.

## Current Problem

현재 구조는 다음 한계가 있다.

- [publishing_store.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_store.py)는 config 파일이 없어도 메모리 기본값만 반환한다.
- [publishing.py](/mnt/c/Users/W/novel_autowriter_2/ui/publishing.py)와 [operations_dashboard.py](/mnt/c/Users/W/novel_autowriter_2/ui/operations_dashboard.py)는 비슷한 readiness 로직을 각자 계산한다.
- [publishing_smoke.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_smoke.py)는 별도 실패 판정을 갖고 있어서, UI에서 본 차단 사유와 smoke 결과가 완전히 같은 언어로 나오지 않는다.

즉, `발행 준비 상태`라는 하나의 개념이 세 군데에 흩어져 있다.

## Approaches

### Option 1. Smoke 실행 시에만 기본 파일 생성

장점:

- 구현이 가장 작다.

단점:

- UI에서 readiness를 먼저 확인하는 흐름과 맞지 않는다.
- 설정 파일이 없는 이유를 늦게 알게 된다.

### Option 2. PublishingStore bootstrap + shared readiness validator

장점:

- 가장 일관된다.
- UI와 smoke가 같은 기준으로 누락 항목을 본다.
- 프로젝트를 처음 열었을 때부터 실제 설정 파일이 존재한다.

단점:

- 작은 helper/module이 하나 더 생긴다.

### Option 3. 별도 setup wizard 추가

장점:

- 운영 UX는 가장 좋다.

단점:

- 지금은 과하다.
- 실운영 준비 slice의 범위를 넘는다.

이번 slice는 Option 2를 선택한다.

## Architecture

### 1. PublishingStore bootstrap

[publishing_store.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_store.py)에 다음 경계를 추가한다.

- `ensure_config_exists()`
  - `publishing/` 디렉터리와 `publishing/config.json`이 없으면 기본 파일을 생성한다.
- `load_config()`
  - 먼저 `ensure_config_exists()`를 호출한 뒤 설정을 읽는다.

이렇게 하면 프로젝트가 publishing 기능을 한 번이라도 읽는 순간, 실제 기준 파일이 디스크에 생긴다.

### 2. Shared readiness validator

새 모듈 `core/publishing_readiness.py`를 둔다.

책임은 하나다:

- 프로젝트 발행 준비 상태를 공통 snapshot으로 계산

입력:

- `project_name`
- `publishing_config`
- `credential_loader`

출력 예시:

- `platform_rows`
- `enabled_platform_count`
- `ready_platform_count`
- `blockers`
- `recommended_actions`
- `config_exists`

platform row는 최소한 다음 필드를 가진다.

- `platform_name`
- `enabled`
- `has_credentials`
- `has_work_id`
- `has_upload_url_template`
- `ready`

### 3. UI usage

[publishing.py](/mnt/c/Users/W/novel_autowriter_2/ui/publishing.py)와 [operations_dashboard.py](/mnt/c/Users/W/novel_autowriter_2/ui/operations_dashboard.py)는 더 이상 readiness를 직접 계산하지 않는다.

둘 다 `publishing_readiness` snapshot을 읽고:

- 화면용 label만 붙인다.
- 런타임 상태와 queue/history 같은 화면 전용 정보만 추가한다.

즉 readiness 계산은 한 군데, 화면 포맷만 UI에 남긴다.

### 4. Smoke usage

[publishing_smoke.py](/mnt/c/Users/W/novel_autowriter_2/core/publishing_smoke.py)는 실행 전에 같은 readiness validator를 사용한다.

동작은 다음과 같다.

- config bootstrap
- selected platform readiness 계산
- readiness에서 이미 `credentials missing`, `work_id missing`, `upload_url_template missing`, `platform disabled`가 드러나면 브라우저를 열지 않고 바로 결과 반환
- readiness를 통과한 플랫폼만 실제 smoke 실행

즉 smoke는 브라우저 테스트 이전에 `정적 준비 상태`를 먼저 검사한다.

## Data Flow

### Project open / UI load

1. `PublishingStore.load_config()` 호출
2. 없으면 `publishing/config.json` bootstrap
3. `publishing_readiness.build_snapshot(...)` 호출
4. UI가 snapshot을 그대로 렌더

### Smoke run

1. `PublishingStore.load_config()` 호출
2. 없으면 bootstrap
3. 선택 플랫폼 기준 readiness snapshot 계산
4. 준비되지 않은 플랫폼은 즉시 실패 리포트
5. 준비된 플랫폼만 `login -> smoke_check_editor`

## Failure Handling

이번 slice에서는 다음을 `requires_user_action` 계열로 본다.

- platform disabled
- credentials missing
- work_id missing
- upload_url_template missing

이 실패들은 adapter 버그가 아니라 운영 준비 미완료다. 따라서 smoke는 이 경우 브라우저를 열지 않는다.

반대로 readiness를 통과했는데 smoke에서 실패하면, 그때부터는 selector/login/platform 쪽 버그 후보로 본다.

## Testing

다음 테스트를 추가/정리한다.

### PublishingStore

- config 파일이 없을 때 `load_config()`가 실제 `publishing/config.json`을 생성하는지
- bootstrap 후 기본 구조가 `DEFAULT_PUBLISHING_CONFIG`와 일치하는지

### Publishing readiness

- enabled platform에 계정, work_id, upload_url_template가 다 있으면 `ready=True`
- 하나라도 없으면 blocker와 recommended action이 생성되는지
- disabled platform은 `ready=False`지만 운영 준비 미완료가 아닌 비활성으로만 표시되는지

### UI

- `ui/publishing.py`가 shared readiness snapshot을 사용해 readiness card를 만드는지
- `ui/operations_dashboard.py`가 같은 blocker/action 언어를 재사용하는지

### Smoke

- readiness 미통과 플랫폼은 browser client를 만들지 않고 즉시 실패하는지
- readiness 통과 플랫폼만 smoke_check_editor로 가는지

## Non-goals

- setup wizard 추가
- work_id 자동 탐색
- selector 자동 수집
- smoke 결과를 설정값으로 역추론해 자동 저장
- 5~6단계 기능

## Expected Outcome

이 변경 후에는:

- 프로젝트마다 실제 `publishing/config.json`이 존재하고
- UI와 smoke가 같은 준비 상태 기준을 공유하며
- 운영자는 “왜 smoke가 안 도는지”를 먼저 readiness snapshot에서 보고
- readiness를 통과한 뒤에만 실제 플랫폼 smoke로 넘어가게 된다

이게 `1~4단계` 마감 이후 필요한 가장 작은 실운영 준비 경계다.
