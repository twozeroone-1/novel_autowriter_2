# Plot Store Boundary Design

## 배경

`workspace`의 Story Bible/State 경계와 `chapters`의 context 반영 경계는 대부분 구조화 저장소 기준으로 정리됐다. 하지만 장기 플롯은 아직 예외다.

- [context.py](/mnt/c/Users/W/novel_autowriter_2/core/context.py) 는 `plot_outline`와 `plot_version`을 여전히 `config.json`에서 읽고 쓴다.
- [planning.py](/mnt/c/Users/W/novel_autowriter_2/ui/planning.py) 는 생성된 플롯을 `generator.ctx.save_plot_outline(...)`로 저장하고 다시 `get_plot_outline()`로 불러온다.
- [chapters.py](/mnt/c/Users/W/novel_autowriter_2/ui/chapters.py), [automation.py](/mnt/c/Users/W/novel_autowriter_2/ui/automation.py), [reviewer.py](/mnt/c/Users/W/novel_autowriter_2/core/reviewer.py)는 모두 `get_plot_outline()`에 기대고 있다.

즉 plot은 UI와 프롬프트 경계에서는 별도 개념처럼 취급되지만, 저장 경계만 아직 레거시 `config.json`에 묶여 있다. 이 상태로는 `config.json`을 호환 저장소로 더 뒤로 밀어내기 어렵다.

## 목표

이번 단계의 목표는 세 가지다.

1. `plot_outline`와 `plot_version`을 전용 저장 경계로 분리한다.
2. 생성, 검수, 자동화, 플래닝 UI는 기존 public API를 유지한 채 새 저장 경계를 사용하게 만든다.
3. 레거시 `config.json`은 호환용으로만 유지하고, plot 읽기/쓰기의 기준선은 새 저장소로 옮긴다.

## 선택지

### 옵션 1. 현 상태 유지

- plot은 계속 `config.json`에 둔다.
- 다른 경계만 구조화 저장소로 관리한다.

장점:
- 구현 비용이 가장 낮다.

단점:
- plot만 레거시 저장에 남아 context 구조가 비대칭이 된다.
- 다음 단계의 `config.json` 축소 작업이 계속 막힌다.

### 옵션 2. plot 전용 저장소만 추가하고 public API는 유지

- `plot_outline`와 `plot_version`을 위한 작은 저장소를 추가한다.
- `ContextManager.get_plot_outline()` / `save_plot_outline()`는 그대로 두고 내부 구현만 새 저장소로 바꾼다.
- 필요하면 legacy config는 호환용 shadow copy 정도만 유지한다.

장점:
- 가장 작은 단계로 저장 경계만 분리할 수 있다.
- `planning`, `chapters`, `automation`, `reviewer`는 호출부를 거의 안 바꿔도 된다.

단점:
- `ContextManager` 안에 호환 계층이 조금 더 남는다.

### 옵션 3. plot까지 포함한 통합 프로젝트 메타 저장소 도입

- Story Bible, State, Plot을 한 번에 관리하는 새 프로젝트 메타 저장소를 만든다.
- `ContextManager`와 여러 UI가 모두 그 저장소를 직접 읽게 바꾼다.

장점:
- 장기적으로는 가장 깔끔할 수 있다.

단점:
- 이번 단계 범위를 넘긴다.
- 이미 정리된 Story Bible/State 경계를 다시 흔들 위험이 있다.

이번 단계는 옵션 2를 채택한다.

## 설계

### 1. `PlotStore` 추가

새 저장소는 plot 전용으로 작게 둔다.

예상 책임:

- 현재 프로젝트의 `plot_outline`
- 현재 `plot_version`
- 기본값/정규화
- 저장/로드

예상 위치:

- 새 파일: `core/plot_store.py`

예상 데이터 형태:

```json
{
  "plot_outline": "",
  "plot_version": "0"
}
```

예상 경로:

- `data/projects/<project>/plot.json`

핵심은 plot을 Story Bible이나 workspace snapshot에 섞지 않고, 별도 저장 단위로 유지하는 것이다.

### 2. `ContextManager`의 plot public API는 유지

다음 public API는 그대로 유지한다.

- `get_plot_outline()`
- `save_plot_outline(plot_text)`
- `build_plot_block(...)`

내부 구현만 바뀐다.

- `get_plot_outline()`는 `PlotStore`에서 읽는다.
- `save_plot_outline()`는 `PlotStore`의 버전 증가 규칙을 사용한다.
- 필요하면 legacy `config.json`의 `plot_outline` / `plot_version`은 호환용으로 동기화하지만, 기준선은 `PlotStore`다.

이렇게 해야 [planning.py](/mnt/c/Users/W/novel_autowriter_2/ui/planning.py), [chapters.py](/mnt/c/Users/W/novel_autowriter_2/ui/chapters.py), [automation.py](/mnt/c/Users/W/novel_autowriter_2/ui/automation.py), [reviewer.py](/mnt/c/Users/W/novel_autowriter_2/core/reviewer.py) 호출부를 대규모로 건드리지 않아도 된다.

### 3. 호환 규칙

이번 단계에서는 backwards compatibility를 끊지 않는다.

권장 규칙:

- 새 저장소가 있으면 그것을 우선한다.
- 새 저장소가 없고 legacy config에만 plot이 있으면 한 번 읽어올 수 있다.
- 새 저장소로 저장한 뒤에는 legacy config도 shadow update 해서 구버전 흐름을 깨지 않는다.

즉 읽기 우선순위는:

1. `plot.json`
2. `config.json` fallback

쓰기 우선순위는:

1. `plot.json`
2. 필요시 `config.json` shadow write

이 단계의 목적은 “기준선 이동”이지 “호환 계층 제거”가 아니다.

### 4. UI와 프롬프트 경계 영향

호출부는 가급적 유지한다.

- `planning`:
  - 저장된 plot 불러오기/저장하기 UX 유지
- `chapters`:
  - 생성 탭, 검수 탭, 반자동 탭의 “저장한 플롯 반영” 체크박스 동작 유지
- `automation`:
  - 저장 플롯 존재 여부에 따른 옵션 활성/비활성 유지
- `reviewer`:
  - `include_plot=True`일 때 새 저장 경계 기준 plot block 사용

이번 단계에서 UI 문구나 workflow는 바꾸지 않는다.

### 5. 테스트 전략

필수 테스트는 세 묶음이다.

- `tests/test_plot_store.py`
  - 기본값 로드
  - 저장 시 버전 증가
  - 저장/로드 round-trip
- `tests/test_context_manager.py`
  - `get_plot_outline()`가 새 저장소를 우선 읽는지
  - `save_plot_outline()`가 새 저장소와 legacy shadow를 일관되게 갱신하는지
  - `build_generation_prompt(... include_plot=True ...)`가 기존처럼 plot block을 포함하는지
- 기존 UI/검수 회귀
  - `tests/test_reviewer.py`
  - 필요하면 `tests/test_ui_helpers.py` 또는 plot 존재 여부를 간접 확인하는 관련 테스트

이번 단계에서는 actual prompt behavior를 유지하는 회귀가 중요하다.

## 비목표

이번 단계에서 하지 않는 것:

- plot을 Canon DB에 구조화 병합하기
- plot을 workspace snapshot에 포함시키기
- planning UI 자체 재설계
- Story Bible / State 저장 경계 재수정
- `config.json` 완전 제거

## 완료 기준

다음이 만족되면 이번 단계는 완료다.

1. `plot_outline` / `plot_version`의 기준 저장 위치가 새 plot 전용 저장소가 된다.
2. `ContextManager`의 plot public API는 유지되고, 주요 호출부는 변경 없이 동작한다.
3. plot 관련 테스트와 기존 origin 회귀가 통과한다.
