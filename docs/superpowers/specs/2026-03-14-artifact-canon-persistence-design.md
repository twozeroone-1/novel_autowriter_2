# Artifact Canon Persistence Design

## 배경

현재 `_2`는 `CanonExtractor`와 publish-time Canon gating까지 갖췄다. 하지만 구조화 후보 저장 경계가 아직 느슨하다.

- `Automator`는 최종 수정본에서 `canon_update` 후보를 만들 수 있다.
- `PublishingRuntime`은 provided candidate가 없으면 extractor fallback을 다시 호출한다.
- `EpisodeArtifactStore`는 회차 artifact만 저장하고 Canon 후보는 저장하지 않는다.
- 더 큰 문제로, 현재 `Generator.save_markdown_document()`는 모든 `.md` 저장에 대해 episode artifact draft를 만들고 있어 초안/검수리포트까지 manifest에 섞일 수 있다.

이 상태는 비용과 재현성 둘 다 좋지 않다.

## 목표

이번 단계의 목표는 세 가지다.

1. 최종 회차 기준 `canon_update` 후보를 episode artifact 영역에 영속화한다.
2. publish runtime은 저장된 후보를 extractor fallback보다 우선 사용한다.
3. 초안/검수리포트가 episode artifact manifest를 오염시키지 않게 저장 경계를 바로잡는다.

## 선택지

### 옵션 1. Manifest inline payload

- `manifest["episodes"][episode_id]["canon_update"] = {...}`

장점:
- 구현이 빠르다.

단점:
- manifest가 비대해진다.
- 회차 메타데이터와 구조화 payload가 한 파일에서 섞여 diff 품질이 나빠진다.

### 옵션 2. Separate JSON file + manifest path

- payload는 `episodes/canon_updates/<episode_id>.json`
- manifest는 `canon_update_path` 같은 참조만 가짐

장점:
- 메타데이터와 payload가 분리된다.
- episode 단위 백업/복사/검사가 쉽다.
- publish/runtime이 재사용하기 좋다.

단점:
- 파일 하나가 더 생긴다.

### 옵션 3. Stage-specific copies

- `draft`, `publishable`, `published` 단계마다 별도 Canon 후보 파일을 둔다.

장점:
- 상태별 재현성은 좋다.

단점:
- 현재 단계에는 과하다.
- 복사/동기화 비용이 생긴다.

이번 단계는 옵션 2를 채택한다.

## 설계

### 1. EpisodeArtifactStore 확장

`EpisodeArtifactStore`에 다음을 추가한다.

- `canon_updates_dir`
- `save_canon_update(episode_id, payload) -> dict`
- `load_canon_update(episode_id) -> dict | None`

저장 위치:

```text
episodes/
  drafts/ep_001.md
  publishable/ep_001.md
  published/ep_001.md
  canon_updates/ep_001.json
  manifests.json
```

manifest episode entry에는 다음만 추가한다.

- `canon_update_path`

payload 자체는 manifest에 넣지 않는다.

### 2. Generator 저장 경계 수정

현재 `save_markdown_document()`는 초안/검수리포트도 episode artifact draft로 만들고 있다. 이건 잘못된 경계다.

변경 원칙:

- `save_markdown_document()` 기본값은 artifact 미생성
- 최종 회차 저장만 episode artifact 생성

이를 위해 `Generator`에는 다음 두 경계를 둔다.

- 일반 문서 저장: 초안, 검수리포트, 기타 markdown
- canonical episode 저장: 최종 회차와 episode artifact metadata

즉, `save_chapter()`는 canonical episode 저장을 담당하고, `Automator`는 이 경로를 사용해 `episode_id`를 안정적으로 받는다.

### 3. Automator 연계

`Automator.run_single_cycle()`는 최종 회차 저장 시 canonical episode metadata를 함께 받는다.

그 후:

- `canon_update` 추출 성공 시 `EpisodeArtifactStore.save_canon_update(episode_id, payload)` 호출
- 결과 객체에는 기존처럼 `canon_update`도 남김
- 필요하면 `canon_update_path`도 결과에 포함 가능

추출 실패 시:

- artifact 파일은 생성하지 않는다
- `canon_update_error`만 남긴다

### 4. Chapter source / Publishing runtime 소비

`load_chapter_source()` 또는 publish runtime은 저장된 Canon 후보를 우선 읽을 수 있어야 한다.

우선순위는 다음으로 고정한다.

1. `result["canon_update"]`
2. `job["canon_update"]`
3. `EpisodeArtifactStore.load_canon_update(episode_id)`
4. extractor fallback

이렇게 하면 자동화로 생성된 회차는 publish 시점 재추출 비용을 줄일 수 있다.

### 5. 테스트 전략

필수 테스트는 네 묶음이다.

- `EpisodeArtifactStore`
  - canon_update 저장/로드
  - manifest에 path 기록
- `Generator`
  - 일반 markdown 저장은 episode artifact를 만들지 않음
  - `save_chapter()`는 episode artifact를 생성
- `Automator`
  - 추출 성공 시 artifact store에 canon_update 저장
- `PublishingRuntime`
  - artifact candidate를 extractor보다 우선 사용

## 비목표

이번 단계에서 하지 않는 것:

- stage별 canon_update 복사본
- workspace UI에서 canon_update 직접 편집
- manifest에 canon_update payload inline 저장

## 완료 기준

다음이 만족되면 이번 단계는 완료다.

1. episode artifact manifest는 최종 회차만 관리한다.
2. `episodes/canon_updates/<episode_id>.json`가 생성될 수 있다.
3. publish runtime이 artifact candidate를 extractor fallback보다 우선 사용한다.
4. 관련 저장/발행/회귀 테스트가 통과한다.
