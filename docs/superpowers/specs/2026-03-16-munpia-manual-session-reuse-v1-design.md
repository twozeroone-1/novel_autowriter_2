# Munpia Manual Session Reuse V1

## Goal

문피아가 자동화 브라우저 로그인에 보안 점검 페이지를 반환할 때, 아이디/비밀번호 자동 입력 대신 사용자가 직접 로그인한 세션을 저장하고 재사용할 수 있게 한다.

## Scope

- 문피아 전용 수동 로그인 세션 bootstrap 경계 추가
- 프로젝트별 문피아 Playwright `storage_state` 파일 저장
- 문피아 client가 저장된 세션을 우선 사용하도록 변경
- smoke/publishing이 세션 부재 시 명확한 안내를 반환하도록 개선

## Non-goals

- 문피아 anti-bot 우회
- 세션 자동 갱신
- 노벨피아 session reuse
- UI에서 전체 세션 관리 기능 제공

## Design

### 1. Session Store

프로젝트별 `publishing/sessions/munpia.json`을 storage state 파일 경로로 사용한다.

### 2. Browser Session

`PlaywrightBrowserSession`은 optional `storage_state_path`를 받아 browser context를 해당 상태로 연다. 현재 세션을 파일로 저장하는 `save_storage_state()`도 제공한다.

### 3. Manual Bootstrap Command

새 script가 headed 브라우저로 문피아 로그인 페이지를 열고, 사용자가 직접 로그인한 뒤 엔터를 누르면 storage state를 저장한다.

### 4. Munpia Client Behavior

- 세션 파일이 있으면 `login()`은 아이디/비밀번호 입력 대신 해당 세션이 유효한지 확인하고 성공 처리한다.
- 세션 파일이 없으면 기존 로그인 경로를 사용한다.
- 기존 로그인 경로에서 보안 점검 페이지가 감지되면 `requires_user_action`으로 `manual session bootstrap` 안내를 반환한다.

### 5. Smoke / Publishing Boundary

문피아 smoke/publish는 세션 파일이 있으면 그 세션을 사용한다. 세션이 없고 보안 점검에 막히면 재시도 오류가 아니라 수동 개입 필요로 분류한다.

## Testing

- session store path resolution
- `PlaywrightBrowserSession` storage state save/load 경계
- 문피아 client가 session file을 우선 사용하는지
- 보안 점검 차단 시 안내 메시지가 bootstrap 방향으로 나가는지
- bootstrap script가 세션 파일 경로를 받아 저장 루틴을 호출하는지
