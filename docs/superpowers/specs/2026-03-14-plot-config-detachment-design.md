# Plot Config Detachment Design

## 배경

이전 단계에서 plot의 기준 저장 위치는 `plot.json`으로 옮겼고, [plot_store.py](/mnt/c/Users/W/novel_autowriter_2/core/plot_store.py)와 [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)는 새 저장소를 우선 사용하도록 바뀌었다. 하지만 일반 config 계약에는 아직 plot 흔적이 남아 있다.

- [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py)의 `DEFAULT_CONFIG`는 여전히 `plot_outline`과 `plot_version`을 포함한다.
- `get_config()`와 `save_config()`도 여전히 “plot이 일반 config 필드의 일부”인 것처럼 보이게 만든다.
- 일부 테스트는 plot 저장을 검증할 때도 `save_config({... plot_outline ...})`를 사용한다.
- 결과적으로 저장 기준선은 이미 `plot.json`으로 옮겼는데, 코드 계약은 아직 `config.json` 중심 시대의 모양을 유지하고 있다.

이 상태는 “실제 기준선”과 “코드가 암시하는 기준선”이 어긋난 상태다. 다음 단계에서는 plot을 일반 workspace/config 계약에서 더 명시적으로 분리해야 한다.

## 목표

이번 단계의 목표는 세 가지다.

1. `ContextManager`의 일반 config 계약에서 plot을 더 이상 주 저장 필드처럼 보이지 않게 한다.
2. plot을 쓰는 경계는 `get_plot_outline()` / `save_plot_outline()` / `build_plot_block()`로 더 분명히 제한한다.
3. 구버전 프로젝트의 `config.json` plot 필드는 읽기 fallback으로만 남기고, 일반 저장 흐름에서는 더 이상 의미 있는 입력 채널로 취급하지 않는다.

## 선택지

### 옵션 1. 현 상태 유지

- plot의 기준선은 `plot.json`이지만, `DEFAULT_CONFIG`와 `save_config()`에는 계속 plot 필드를 남긴다.

장점:
- 추가 변경이 거의 없다.

단점:
- 새 경계가 코드 계약에 반영되지 않는다.
- 이후 유지보수 시 “plot은 config에 넣어도 된다”는 잘못된 신호를 계속 준다.

### 옵션 2. 일반 config 계약에서 plot 필드를 제거하고, plot API만 남긴다

- `DEFAULT_CONFIG`에서 plot 관련 필드를 뺀다.
- `get_config()` / `get_workspace_settings()` / `save_config()`는 plot을 일반 설정 항목으로 다루지 않는다.
- plot 저장/로드는 오직 `get_plot_outline()` / `save_plot_outline()` 경계만 사용한다.
- 다만 `config.json`에 이미 있는 plot 값은 fallback migration 소스로만 읽는다.

장점:
- 현재 저장 기준선과 코드 계약이 일치한다.
- Story Bible/State와 Plot의 경계가 더 선명해진다.

단점:
- 테스트와 일부 레거시 가정들을 같이 정리해야 한다.

### 옵션 3. 레거시 plot fallback도 즉시 제거

- `plot.json`이 없으면 plot은 없는 것으로 간주한다.
- `config.json`의 plot 필드는 완전히 무시한다.

장점:
- 가장 깔끔하다.

단점:
- 기존 프로젝트 호환성이 불필요하게 깨질 수 있다.
- 지금 단계로는 공격적이다.

이번 단계는 옵션 2를 채택한다.

## 설계

### 1. 일반 config 계약 정리

이번 단계의 핵심은 “plot은 일반 config의 일부가 아니다”를 코드 구조로 드러내는 것이다.

권장 변경:

- `DEFAULT_CONFIG`에서 `plot_outline`, `plot_version` 제거
- `get_config()`는 Story Bible/State/summary 중심 snapshot만 반환
- `save_config()`는 Story Bible/State 쪽 호환 저장 경계만 담당

즉 plot은 `config.json`에 shadow로 남을 수는 있어도, 일반 config API의 공식 입력/출력 항목은 아니게 만든다.

### 2. plot fallback은 전용 helper에 가둔다

plot의 legacy fallback은 계속 필요하다. 다만 이건 일반 config 로직에 섞이면 안 된다.

권장 구조:

- plot fallback용 helper는 `ContextManager` 내부 전용으로 유지
- 새 store가 있으면 `plot.json`
- 없으면 `config.json`의 legacy plot 필드
- 이 fallback은 `get_plot_outline()` / `save_plot_outline()` 내부에서만 사용

즉 “legacy config에서 plot 읽기”는 일반 설정 로직이 아니라 plot 전용 migration/compatibility 로직이 된다.

### 3. 저장 규칙

일반 저장 흐름과 plot 저장 흐름을 분리한다.

- `save_config(config_data)`
  - plot 관련 입력은 무시하거나 제거된 것으로 본다
  - Story Bible/State 관련 필드만 반영한다
- `save_plot_outline(plot_text)`
  - `plot.json` 기준 저장
  - legacy `config.json` shadow는 필요 시 전용 helper로만 동기화한다

중요한 점은 `save_config()`가 더 이상 plot 업데이트 경로가 아니어야 한다는 것이다.

### 4. 테스트 정리 방향

이 단계에서는 테스트도 새 계약을 따르게 바꿔야 한다.

필수 변경 방향:

- [test_context_manager.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_context_manager.py)
  - plot prompt 테스트는 `save_config({... plot_outline ...})` 대신 `save_plot_outline(...)`를 사용
  - 필요하면 `get_config()`가 plot 키를 포함하지 않는다는 테스트 추가
  - 필요하면 `save_config()`가 plot 필드를 공식적으로 보장하지 않는다는 테스트 추가
- [test_plot_store.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_plot_store.py)
  - 기존 유지
- [test_reviewer.py](/mnt/c/Users/W/novel_autowriter_2/tests/test_reviewer.py)
  - 기존 유지 가능, reviewer는 이미 plot API만 사용 중

이 단계의 테스트 목표는 “plot이 여전히 동작한다”와 “하지만 일반 config 계약에는 속하지 않는다”를 동시에 증명하는 것이다.

### 5. UI와 런타임 영향

이번 단계에서 production 호출부는 대체로 유지된다.

- `planning`
  - 계속 `save_plot_outline()` / `get_plot_outline()` 사용
- `chapters`
  - 계속 저장된 plot 존재 여부만 확인
- `automation`
  - 계속 저장된 plot 존재 여부만 확인
- `reviewer`
  - 계속 plot API만 사용

즉 이번 단계는 UI 변경이 아니라 내부 계약 정리다.

## 비목표

이번 단계에서 하지 않는 것:

- plot fallback 완전 제거
- `plot.json` schema 확장
- planning/chapters/automation UI 재설계
- Story Bible/State 저장 경계 재수정
- automation/publishing config 저장소 변경

## 완료 기준

다음이 만족되면 이번 단계는 완료다.

1. 일반 config 계약에서 plot이 주 저장 필드처럼 노출되지 않는다.
2. plot은 `get_plot_outline()` / `save_plot_outline()` 경계로만 다뤄진다.
3. plot 관련 prompt/reviewer 동작은 유지되고, 기존 origin 회귀가 통과한다.
