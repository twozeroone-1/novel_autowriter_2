import threading
from datetime import date, datetime, time as dt_time
from uuid import uuid4

import streamlit as st

from core.platform_clients.base import PlatformError, PlatformWorkMetadata
from core.platform_clients.munpia import MunpiaClient
from core.platform_clients.novelpia import NovelpiaClient
from core.publishing_executor import PublishingExecutor
from core.publishing_runtime import PublishingRuntime, run_publishing_pass
from core.publishing_store import PublishingStore
from core.platform_credentials import (
    load_platform_credentials,
    save_platform_credentials,
)


PLATFORM_LABELS = {
    "munpia": "문피아",
    "novelpia": "노벨피아",
}
PLATFORM_OPTIONS = tuple(PLATFORM_LABELS.keys())
WEEKDAY_LABELS = {
    "mon": "월",
    "tue": "화",
    "wed": "수",
    "thu": "목",
    "fri": "금",
    "sat": "토",
    "sun": "일",
}
WEEKDAY_OPTIONS = tuple(WEEKDAY_LABELS.keys())
NOVELPIA_GENRE_LABELS = {
    "": "선택",
    "1": "판타지",
    "2": "무협",
    "3": "현대",
    "5": "고수위",
    "6": "로맨스",
    "7": "대체역사",
    "8": "스포츠",
    "9": "SF",
    "10": "기타",
    "11": "패러디",
    "12": "현대판타지",
    "13": "라이트노벨",
    "14": "공포",
}


def build_schedule_editor_state(schedule_type: str) -> dict[str, bool]:
    return {
        "show_time": schedule_type in {"daily", "weekly"},
        "show_days": schedule_type == "weekly",
        "show_hours": schedule_type == "interval",
    }


def format_publishing_schedule_summary(config: dict) -> str:
    if not config.get("enabled", False):
        return "비활성"

    schedule = config.get("schedule", {})
    schedule_type = schedule.get("type", "daily")
    if schedule_type == "daily":
        return f"매일 {schedule.get('time', '21:00')}"
    if schedule_type == "weekly":
        days = schedule.get("days", [])
        labels = [WEEKDAY_LABELS.get(day, str(day)) for day in days]
        return f"매주 {', '.join(labels)} {schedule.get('time', '21:00')}".strip()
    if schedule_type == "interval":
        return f"{int(schedule.get('hours', 24))}시간마다 반복"
    return "설정 없음"


def format_publishing_runtime_status(runtime: dict) -> str:
    status = runtime.get("status", "idle")
    error = str(runtime.get("last_error", "")).strip()
    if status == "running":
        return "실행 중"
    if status == "cooldown":
        return f"쿨다운: {error}" if error else "쿨다운"
    if status == "blocked":
        return f"차단됨: {error}" if error else "차단됨"
    if status == "stopped":
        return f"중단됨: {error}" if error else "중단됨"
    if status == "paused":
        return f"일시중지: {error}" if error else "일시중지"
    return "대기 중"


def format_publishing_runtime_detail_value(value) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    return text or "-"


def summarize_selected_platforms(targets: dict) -> str:
    labels = [
        PLATFORM_LABELS[platform_name]
        for platform_name, payload in targets.items()
        if platform_name in PLATFORM_LABELS and payload.get("selected")
    ]
    return ", ".join(labels) if labels else "-"


def count_pending_publishing_jobs(queue: list[dict]) -> int:
    return sum(1 for job in queue if job.get("status") in {"pending", "partial_failed"})


def build_publishing_queue_rows(queue: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for index, job in enumerate(queue, start=1):
        rows.append(
            {
                "순서": index,
                "회차": job.get("chapter_title", ""),
                "상태": job.get("status", "pending"),
                "대상": summarize_selected_platforms(job.get("targets", {})),
                "시도": int(job.get("attempt_count", 0)),
            }
        )
    return rows


def build_publishing_history_rows(history: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for record in history:
        rows.append(
            {
                "시간": record.get("timestamp", ""),
                "회차": record.get("chapter_title", ""),
                "결과": "성공" if record.get("success") else "실패",
                "플랫폼": summarize_selected_platforms(
                    {
                        platform_name: {"selected": True}
                        for platform_name in record.get("platform_results", {}).keys()
                    }
                ),
                "오류": _extract_history_error(record.get("platform_results", {})),
            }
        )
    return rows


def build_publishing_history_summary(history: list[dict]) -> dict[str, int]:
    total = len(history)
    success = sum(1 for record in history if record.get("success"))
    return {
        "total": total,
        "success": success,
        "failure": total - success,
    }


class PublishingBackgroundService:
    def __init__(self, poll_seconds: int = 30):
        self.poll_seconds = poll_seconds
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_loop,
            name="publishing-background-service",
            daemon=True,
        )
        self._thread.start()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                run_publishing_pass(
                    now=datetime.now().astimezone(),
                    executor_factory=lambda project_name: PublishingExecutor(project_name=project_name),
                )
            except Exception:
                pass
            self._stop_event.wait(self.poll_seconds)


def render_publishing_tab(app) -> None:
    project_name = app.generator.ctx.project_name
    store = PublishingStore(project_name=project_name)
    config = store.load_config()
    queue = store.load_queue()
    runtime = store.load_runtime()
    history = store.load_recent_history(limit=10)

    st.header("[6] 외부 플랫폼 업로드")
    st.caption("문피아/노벨피아 계정과 작품 매핑을 관리하고, 로컬 회차 파일을 예약 업로드합니다.")

    summary_col1, summary_col2, summary_col3 = st.columns(3)
    with summary_col1:
        st.metric("업로드 스케줄", format_publishing_schedule_summary(config))
    with summary_col2:
        st.metric("현재 상태", format_publishing_runtime_status(runtime))
    with summary_col3:
        st.metric("대기 작업", str(count_pending_publishing_jobs(queue)))

    st.divider()
    st.subheader("1. 플랫폼 계정/작품 설정")
    for platform_name in PLATFORM_OPTIONS:
        _render_platform_settings(project_name, store, config, platform_name)

    st.divider()
    st.subheader("2. 업로드 스케줄 설정")
    _render_schedule_settings(store, config)

    st.divider()
    st.subheader("3. 업로드 큐")
    _render_queue_editor(app, store, config, queue)

    st.divider()
    st.subheader("4. 실행 상태와 이력")
    _render_runtime_and_history(project_name, store, runtime, history)


def _render_platform_settings(project_name: str, store: PublishingStore, config: dict, platform_name: str) -> None:
    platform_config = config.get("platforms", {}).get(platform_name, {})
    credentials = load_platform_credentials(project_name, platform_name)
    label = PLATFORM_LABELS[platform_name]

    with st.expander(f"{label} 설정", expanded=False):
        with st.form(f"{platform_name}_settings_form"):
            enabled = st.checkbox(
                f"{label} 업로드 활성화",
                value=platform_config.get("enabled", False),
                key=f"publishing_{platform_name}_enabled",
            )
            username = st.text_input(
                f"{label} 아이디",
                value=credentials.get("username", ""),
                key=f"publishing_{platform_name}_username",
            )
            password = st.text_input(
                f"{label} 비밀번호",
                value=credentials.get("password", ""),
                type="password",
                key=f"publishing_{platform_name}_password",
            )
            work_id = st.text_input(
                f"{label} 작품 ID",
                value=platform_config.get("work_id", ""),
                key=f"publishing_{platform_name}_work_id",
            )
            work_title = st.text_input(
                f"{label} 작품명",
                value=platform_config.get("work_title", ""),
                key=f"publishing_{platform_name}_work_title",
            )
            work_description = st.text_area(
                f"{label} 작품 소개",
                value=platform_config.get("work_description", ""),
                height=120,
                key=f"publishing_{platform_name}_work_description",
            )
            if platform_name == "novelpia":
                current_genre = str(platform_config.get("genre", "")).strip()
                if current_genre not in NOVELPIA_GENRE_LABELS:
                    current_genre = ""
                genre = st.selectbox(
                    f"{label} 메인 장르",
                    options=list(NOVELPIA_GENRE_LABELS.keys()),
                    index=list(NOVELPIA_GENRE_LABELS.keys()).index(current_genre),
                    format_func=lambda value: NOVELPIA_GENRE_LABELS[value],
                    help="노벨피아 신규 작품 생성 시 필수입니다.",
                    key=f"publishing_{platform_name}_genre",
                )
            else:
                genre = st.text_input(
                    f"{label} 장르",
                    value=str(platform_config.get("genre", "")).strip(),
                    key=f"publishing_{platform_name}_genre",
                )
            create_work_url = st.text_input(
                f"{label} 작품 생성 URL",
                value=platform_config.get("create_work_url", ""),
                key=f"publishing_{platform_name}_create_work_url",
            )
            upload_url_template = st.text_input(
                f"{label} 회차 업로드 URL 템플릿",
                value=platform_config.get("upload_url_template", ""),
                help="예: https://example.com/work/{work_id}/episode/new",
                key=f"publishing_{platform_name}_upload_url_template",
            )
            default_visibility = st.selectbox(
                f"{label} 기본 공개 설정",
                options=["public", "private"],
                index=["public", "private"].index(platform_config.get("default_publish_visibility", "public")),
                key=f"publishing_{platform_name}_default_visibility",
            )
            age_grade = st.selectbox(
                f"{label} 기본 연령 등급",
                options=["general", "adult"],
                index=["general", "adult"].index(platform_config.get("default_age_grade", "general")),
                key=f"publishing_{platform_name}_default_age_grade",
            )

            save_clicked = st.form_submit_button(
                "플랫폼 설정 저장",
                use_container_width=True,
                key=f"publishing_{platform_name}_save",
            )
            create_clicked = st.form_submit_button(
                "신규 작품 생성",
                use_container_width=True,
                key=f"publishing_{platform_name}_create",
            )

        if save_clicked or create_clicked:
            config = store.load_config()
            updated_platform_config = config.setdefault("platforms", {}).setdefault(platform_name, {})
            updated_platform_config.update(
                {
                    "enabled": enabled,
                    "work_id": work_id.strip(),
                    "work_title": work_title.strip(),
                    "work_description": work_description.strip(),
                    "genre": str(genre).strip(),
                    "create_work_url": create_work_url.strip(),
                    "upload_url_template": upload_url_template.strip(),
                    "default_publish_visibility": default_visibility,
                    "default_age_grade": age_grade,
                }
            )
            store.save_config(config)

            if username.strip() and password.strip():
                ok, message = save_platform_credentials(project_name, platform_name, username, password)
                if ok:
                    st.success(message)
                else:
                    st.warning(message)

            if save_clicked:
                st.success(f"{label} 설정을 저장했습니다.")
                st.rerun()

            if create_clicked:
                try:
                    created_work_id = _create_platform_work(
                        platform_name=platform_name,
                        username=username,
                        password=password,
                        platform_config=updated_platform_config,
                    )
                except PlatformError as exc:
                    st.error(f"{label} 작품 생성 실패: {exc}")
                except Exception as exc:
                    st.error(f"{label} 작품 생성 중 예기치 않은 오류가 발생했습니다: {exc}")
                else:
                    updated_platform_config["work_id"] = created_work_id
                    store.save_config(config)
                    st.success(f"{label} 작품 생성 완료: `{created_work_id}`")
                    st.rerun()


def _render_schedule_settings(store: PublishingStore, config: dict) -> None:
    schedule = config.get("schedule", {})
    schedule_type = schedule.get("type", "daily")
    default_time = _parse_time_value(schedule.get("time", "21:00"))
    default_days = [day for day in schedule.get("days", []) if day in WEEKDAY_OPTIONS]
    default_hours = int(schedule.get("hours", 24))
    browser_config = config.get("browser", {})

    enabled = st.checkbox("자동 업로드 활성화", value=config.get("enabled", False), key="publishing_enabled")
    headless = st.checkbox(
        "브라우저 headless 모드",
        value=bool(browser_config.get("headless", False)),
        key="publishing_browser_headless",
    )
    max_attempts = int(
        st.number_input(
            "실패 시 최대 재시도 횟수",
            min_value=1,
            max_value=10,
            value=int(config.get("retry_policy", {}).get("max_attempts", 2)),
            step=1,
            key="publishing_retry_attempts",
        )
    )

    selected_type = st.selectbox(
        "스케줄 방식",
        options=["daily", "weekly", "interval"],
        index=["daily", "weekly", "interval"].index(
            schedule_type if schedule_type in {"daily", "weekly", "interval"} else "daily"
        ),
        format_func=lambda value: {
            "daily": "매일 특정 시각",
            "weekly": "요일별 특정 시각",
            "interval": "N시간마다 반복",
        }[value],
        key="publishing_schedule_type",
    )

    editor_state = build_schedule_editor_state(selected_type)
    selected_time = default_time
    selected_days = default_days
    interval_hours = default_hours
    if editor_state["show_time"]:
        selected_time = st.time_input(
            "실행 시각",
            value=default_time,
            step=60,
            key="publishing_schedule_time",
        )
    if editor_state["show_days"]:
        selected_days = st.multiselect(
            "실행 요일",
            options=list(WEEKDAY_OPTIONS),
            default=default_days,
            format_func=lambda value: WEEKDAY_LABELS[value],
            key="publishing_schedule_days",
        )
    if editor_state["show_hours"]:
        interval_hours = int(
            st.number_input(
                "반복 간격(시간)",
                min_value=1,
                max_value=168,
                value=default_hours,
                step=1,
                key="publishing_interval_hours",
            )
        )

    if st.button("업로드 스케줄 저장", type="primary", use_container_width=True, key="publishing_schedule_save"):
        config = store.load_config()
        config["enabled"] = enabled
        config["browser"] = {"headless": headless}
        config["retry_policy"] = {"max_attempts": max_attempts}
        config["schedule"] = {
            "type": selected_type,
            "time": selected_time.strftime("%H:%M"),
            "days": selected_days,
            "hours": interval_hours,
        }
        store.save_config(config)
        st.success("업로드 스케줄을 저장했습니다.")
        st.rerun()


def _render_queue_editor(app, store: PublishingStore, config: dict, queue: list[dict]) -> None:
    chapter_options = _list_project_chapter_files(app)
    today = datetime.now().date()
    now_time = datetime.now().replace(second=0, microsecond=0).time()

    with st.form("publishing_queue_add_form"):
        if chapter_options:
            selected_source_path = st.selectbox(
                "소스 회차 파일",
                options=chapter_options,
                key="publishing_queue_source_path",
            )
        else:
            selected_source_path = st.text_input(
                "소스 회차 파일 경로",
                value="chapters/",
                key="publishing_queue_source_path_manual",
            )
        chapter_title = st.text_input("업로드 회차 제목", value="", key="publishing_queue_title")
        selected_platforms = st.multiselect(
            "대상 플랫폼",
            options=list(PLATFORM_OPTIONS),
            default=[],
            format_func=lambda value: PLATFORM_LABELS[value],
            key="publishing_queue_platforms",
        )
        publish_mode = st.selectbox(
            "발행 방식",
            options=["immediate", "reserved"],
            format_func=lambda value: {"immediate": "즉시 발행", "reserved": "예약 발행"}[value],
            key="publishing_queue_publish_mode",
        )
        visibility = st.selectbox(
            "공개 설정",
            options=["public", "private"],
            format_func=lambda value: {"public": "공개", "private": "비공개"}[value],
            key="publishing_queue_visibility",
        )
        scheduled_date = st.date_input("작업 시작 날짜", value=today, key="publishing_queue_scheduled_date")
        scheduled_time = st.time_input("작업 시작 시각", value=now_time, step=60, key="publishing_queue_scheduled_time")
        reserved_date = scheduled_date
        reserved_time = scheduled_time
        if publish_mode == "reserved":
            reserved_date = st.date_input("사이트 예약 날짜", value=today, key="publishing_queue_reserved_date")
            reserved_time = st.time_input(
                "사이트 예약 시각",
                value=now_time,
                step=60,
                key="publishing_queue_reserved_time",
            )

        add_clicked = st.form_submit_button(
            "업로드 큐에 추가",
            type="primary",
            use_container_width=True,
            key="publishing_queue_add",
        )

    if add_clicked:
        if not selected_source_path.strip():
            st.warning("소스 회차 파일을 선택해 주세요.")
        elif not chapter_title.strip():
            st.warning("업로드 회차 제목을 입력해 주세요.")
        elif not selected_platforms:
            st.warning("대상 플랫폼을 하나 이상 선택해 주세요.")
        else:
            scheduled_at = _combine_date_time(scheduled_date, scheduled_time).isoformat()
            reserved_at = (
                _combine_date_time(reserved_date, reserved_time).isoformat() if publish_mode == "reserved" else None
            )
            queue.append(
                {
                    "id": f"pub_{uuid4().hex[:10]}",
                    "chapter_title": chapter_title.strip(),
                    "source_path": selected_source_path.strip(),
                    "status": "pending",
                    "scheduled_at": scheduled_at,
                    "targets": {
                        platform_name: {
                            "selected": platform_name in selected_platforms,
                            "status": "pending",
                            "work_id": config.get("platforms", {}).get(platform_name, {}).get("work_id", ""),
                            "episode_title": chapter_title.strip(),
                            "publish_mode": publish_mode,
                            "reserved_at": reserved_at,
                            "visibility": visibility,
                        }
                        for platform_name in PLATFORM_OPTIONS
                    },
                    "attempt_count": 0,
                    "created_at": datetime.now().astimezone().isoformat(),
                    "last_error": "",
                }
            )
            store.save_queue(queue)
            st.success("업로드 작업을 큐에 추가했습니다.")
            st.rerun()

    queue_rows = build_publishing_queue_rows(queue)
    if queue_rows:
        st.dataframe(queue_rows, use_container_width=True, hide_index=True)
        selected_job_id = st.selectbox(
            "업로드 작업 선택",
            options=[job.get("id", "") for job in queue],
            format_func=lambda job_id: _format_job_option(queue, job_id),
            key="publishing_selected_job_id",
        )
        action_col1, action_col2, action_col3, action_col4 = st.columns(4)
        with action_col1:
            if st.button("위로 이동", use_container_width=True, key="publishing_queue_move_up"):
                _move_job(queue, selected_job_id, direction=-1)
                store.save_queue(queue)
                st.rerun()
        with action_col2:
            if st.button("아래로 이동", use_container_width=True, key="publishing_queue_move_down"):
                _move_job(queue, selected_job_id, direction=1)
                store.save_queue(queue)
                st.rerun()
        with action_col3:
            if st.button("재시도 상태로 초기화", use_container_width=True, key="publishing_queue_reset"):
                _reset_job(queue, selected_job_id)
                store.save_queue(queue)
                st.rerun()
        with action_col4:
            if st.button("큐에서 제거", use_container_width=True, key="publishing_queue_remove"):
                updated_queue = [job for job in queue if job.get("id") != selected_job_id]
                store.save_queue(updated_queue)
                st.rerun()
    else:
        st.info("아직 등록된 업로드 작업이 없습니다.")


def _render_runtime_and_history(project_name: str, store: PublishingStore, runtime: dict, history: list[dict]) -> None:
    status_col1, status_col2 = st.columns(2)
    with status_col1:
        st.write(f"현재 상태: `{runtime.get('status', 'idle')}`")
        st.write(f"마지막 실행: `{format_publishing_runtime_detail_value(runtime.get('last_run_at'))}`")
    with status_col2:
        st.write(f"현재 작업: `{format_publishing_runtime_detail_value(runtime.get('current_job_id'))}`")
        st.write(f"마지막 오류: `{format_publishing_runtime_detail_value(runtime.get('last_error'))}`")

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button("지금 바로 1회 실행", use_container_width=True, key="publishing_run_once"):
            runtime_runner = PublishingRuntime(
                store=store,
                executor=PublishingExecutor(project_name=project_name),
            )
            runtime_runner.tick(now=datetime.now().astimezone(), force=True)
            st.success("업로드 작업을 1회 실행했습니다.")
            st.rerun()
    with action_col2:
        if st.button("런타임 초기화", use_container_width=True, key="publishing_resume"):
            store.save_runtime(
                {
                    "status": "idle",
                    "current_job_id": None,
                    "last_run_at": runtime.get("last_run_at"),
                    "last_error": "",
                }
            )
            st.success("업로드 런타임을 다시 대기 상태로 돌렸습니다.")
            st.rerun()

    history_summary = build_publishing_history_summary(history)
    summary_col1, summary_col2, summary_col3 = st.columns(3)
    with summary_col1:
        st.metric("최근 실행", str(history_summary["total"]))
    with summary_col2:
        st.metric("성공", str(history_summary["success"]))
    with summary_col3:
        st.metric("실패", str(history_summary["failure"]))

    history_rows = build_publishing_history_rows(history)
    if history_rows:
        st.dataframe(history_rows, use_container_width=True, hide_index=True)
    else:
        st.info("최근 업로드 실행 이력이 없습니다.")


def _list_project_chapter_files(app) -> list[str]:
    chapters_dir = app.generator.chapters_dir
    if not chapters_dir.exists():
        return []
    return [
        f"chapters/{path.name}"
        for path in sorted(chapters_dir.iterdir())
        if path.is_file() and path.suffix == ".md"
    ]


def _create_platform_work(
    *,
    platform_name: str,
    username: str,
    password: str,
    platform_config: dict,
) -> str:
    metadata = PlatformWorkMetadata(
        title=str(platform_config.get("work_title", "")).strip(),
        description=str(platform_config.get("work_description", "")).strip(),
        genre=str(platform_config.get("genre", "")).strip(),
        age_grade=str(platform_config.get("default_age_grade", "general")).strip(),
        cover_path=str(platform_config.get("cover_path", "")).strip(),
    )
    client = _build_platform_client(
        platform_name=platform_name,
        username=username,
        password=password,
        platform_config=platform_config,
        headless=False,
    )
    try:
        client.login()
        result = client.ensure_work(metadata, work_id=str(platform_config.get("work_id", "")).strip())
        if not result.work_id:
            raise PlatformError(f"{PLATFORM_LABELS[platform_name]} 작품 ID를 추출하지 못했습니다.", error_type="retryable")
        return result.work_id
    finally:
        if hasattr(client, "close"):
            client.close()


def _build_platform_client(*, platform_name: str, username: str, password: str, platform_config: dict, headless: bool):
    if platform_name == "munpia":
        return MunpiaClient(
            username=username,
            password=password,
            platform_config=platform_config,
            headless=headless,
        )
    if platform_name == "novelpia":
        return NovelpiaClient(
            username=username,
            password=password,
            platform_config=platform_config,
            headless=headless,
        )
    raise ValueError(f"Unsupported platform: {platform_name}")


def _parse_time_value(raw_time: str) -> dt_time:
    hour_text, minute_text = raw_time.split(":", maxsplit=1)
    return dt_time(hour=int(hour_text), minute=int(minute_text))


def _combine_date_time(day_value: date, time_value: dt_time) -> datetime:
    tzinfo = datetime.now().astimezone().tzinfo
    return datetime.combine(day_value, time_value, tzinfo=tzinfo)


def _format_job_option(queue: list[dict], job_id: str) -> str:
    for index, job in enumerate(queue, start=1):
        if job.get("id") == job_id:
            return f"{index}. {job.get('chapter_title', '')} [{job.get('status', 'pending')}]"
    return job_id


def _move_job(queue: list[dict], job_id: str, *, direction: int) -> None:
    index = next((i for i, job in enumerate(queue) if job.get("id") == job_id), None)
    if index is None:
        return
    new_index = index + direction
    if new_index < 0 or new_index >= len(queue):
        return
    queue[index], queue[new_index] = queue[new_index], queue[index]


def _reset_job(queue: list[dict], job_id: str) -> None:
    for job in queue:
        if job.get("id") == job_id:
            job["status"] = "pending"
            job["attempt_count"] = 0
            job["last_error"] = ""
            for target in job.get("targets", {}).values():
                if isinstance(target, dict) and target.get("selected"):
                    target["status"] = "pending"
            return


def _extract_history_error(platform_results: dict) -> str:
    for payload in platform_results.values():
        error_text = str(payload.get("error_text", "")).strip() if isinstance(payload, dict) else ""
        if error_text:
            return error_text
    return ""
