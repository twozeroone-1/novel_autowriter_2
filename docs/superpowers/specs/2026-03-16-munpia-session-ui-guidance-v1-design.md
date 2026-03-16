# Munpia Session UI Guidance V1

## Goal

`발행 운영` 화면에서 문피아 세션 상태를 바로 확인하고, 수동 세션 bootstrap을 UI에서 시작하거나 최소한 실행 명령을 바로 복사할 수 있게 한다.

## Approaches

1. UI에 안내 문구와 명령만 노출
- 가장 안전하다.
- 하지만 사용자가 다시 터미널로 가야 한다.

2. UI에 별도 터미널 launcher 버튼 추가
- 추천.
- 버튼을 누르면 Windows 쪽 새 터미널에서 `bootstrap_munpia_session.py`를 실행한다.
- 실패하면 같은 화면에 수동 명령을 그대로 보여준다.

3. Streamlit 안에서 직접 headed bootstrap 실행
- 블로킹이 길고, 서버 프로세스와 사용자 상호작용이 충돌하기 쉽다.
- 이번 slice에서는 제외한다.

## Design

- `core/munpia_session_launcher.py`
  - bootstrap 명령 문자열 생성
  - Windows terminal/cmd 기반 launcher best-effort 실행
- `ui/publishing.py`
  - 문피아 설정 expander 안에 `세션 상태` 섹션 추가
  - 세션 파일 존재 여부, 경로, bootstrap 명령 표시
  - `문피아 세션 저장 시작` 버튼 추가
  - launcher 실패 시 수동 실행 명령을 warning으로 노출
- `build_publishing_operations_snapshot(...)`
  - 문피아가 활성화되어 있고 세션 파일이 없으면 next action에 세션 저장 안내 추가

## Non-goals

- 세션 bootstrap UI 내부 완료
- 세션 만료 자동 감지/갱신
- 문피아 anti-bot 우회

## Testing

- bootstrap command 문자열 생성
- launcher 명령 조립
- 문피아 세션 snapshot 생성
- publishing snapshot이 문피아 세션 부족 안내를 포함하는지
