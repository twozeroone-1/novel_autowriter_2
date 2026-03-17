import threading
from datetime import datetime, time as dt_time
from uuid import uuid4

import streamlit as st

from core.automator import Automator
from core.automation_runtime import AutomationRuntime, run_automation_pass
from core.automation_store import AutomationStore
from core.diagnostics import load_recent_llm_runs
from ui.diagnostics import build_diagnostics_status_snapshot, render_diagnostics_panel


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





def build_schedule_editor_state(schedule_type: str) -> dict[str, bool]:
    return {
        "show_time": schedule_type in {"daily", "weekly"},
        "show_days": schedule_type == "weekly",
        "show_hours": schedule_type == "interval",
    }


def format_schedule_summary(config: dict) -> str:
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


def format_runtime_status(runtime: dict) -> str:
    status = runtime.get("status", "idle")
    if status == "running":
        return "실행 중"
    if status == "paused":
        error = str(runtime.get("last_error", "")).strip()
        return f"일시중지: {error}" if error else "일시중지"
    return "대기 중"


def format_runtime_detail_value(value) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    return text or "-"


def build_queue_rows(queue: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for index, job in enumerate(queue, start=1):
        rows.append(
            {
                "순서": index,
                "제목": job.get("title", ""),
                "상태": job.get("status", "pending"),
                "시도": int(job.get("attempt_count", 0)),
                "분량": int(job.get("target_length", 5000)),
            }
        )
    return rows


def build_history_rows(history: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for record in history:
        rows.append(
            {
                "시각": record.get("timestamp", ""),
                "제목": record.get("title", ""),
                "결과": "성공" if record.get("success") else "실패",
                "백엔드": record.get("backend", record.get("actual_backend", "")),
                "오류": record.get("error_text", ""),
            }
        )
    return rows


def build_history_summary(history: list[dict]) -> dict[str, int]:
    total = len(history)
    success = sum(1 for record in history if record.get("success"))
    return {
        "total": total,
        "success": success,
        "failure": total - success,
    }


def _count_pending_jobs(queue: list[dict]) -> int:
    return sum(1 for job in queue if job.get("status") in {"pending", "partial_failed"})


def _build_automation_operations_actions(
    config: dict,
    runtime: dict,
    queue_rows: list[dict],
    diagnostics_snapshot: dict[str, str],
) -> list[str]:
    actions: list[str] = []
    status = str(runtime.get("status", "idle"))
    if status == "paused":
        actions.append("paused 상태를 해제하거나 마지막 오류를 해결하세요.")
    elif not config.get("enabled", False):
        actions.append("자동화를 활성화하고 스케줄을 저장하세요.")

    if not queue_rows:
        actions.append("작업 큐에 다음 회차 작업을 추가하세요.")

    recommended_action = str(diagnostics_snapshot.get("recommended_action", "")).strip()
    if diagnostics_snapshot.get("status") in {"warning", "empty"} and recommended_action:
        actions.append(recommended_action)

    if not actions:
        actions.append("자동화 스케줄과 대기 작업을 확인하세요.")
    return actions


def build_automation_operations_snapshot(
    *,
    config: dict,
    queue: list[dict],
    runtime: dict,
    history: list[dict],
    diagnostics_snapshot: dict[str, str],
) -> dict:
    queue_rows = build_queue_rows(queue)
    history_rows = build_history_rows(history)
    history_summary = build_history_summary(history)
    blockers: list[str] = []

    status = str(runtime.get("status", "idle"))
    if status == "paused":
        error_text = format_runtime_detail_value(runtime.get("last_error"))
        blockers.append(f"일시중지 상태입니다: {error_text}")
    elif not config.get("enabled", False):
        blockers.append("자동화가 비활성화되어 있습니다.")

    warning_text = str(diagnostics_snapshot.get("warning_text", "")).strip()
    if warning_text:
        blockers.append(warning_text)

    if not queue_rows:
        blockers.append("대기 중인 자동화 작업이 없습니다.")

    return {
        "schedule_summary": format_schedule_summary(config),
        "runtime_status": format_runtime_status(runtime),
        "pending_job_count": _count_pending_jobs(queue),
        "history_summary": history_summary,
        "queue_rows": queue_rows,
        "history_rows": history_rows,
        "diagnostics_summary": diagnostics_snapshot.get("summary_text", ""),
        "diagnostics_status": diagnostics_snapshot.get("status", "empty"),
        "blockers": blockers,
        "next_actions": _build_automation_operations_actions(
            config,
            runtime,
            queue_rows,
            diagnostics_snapshot,
        ),
    }


class AutomationBackgroundService:
    def __init__(self, poll_seconds: int = 30):
        self.poll_seconds = poll_seconds
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_loop,
            name="automation-background-service",
            daemon=True,
        )
        self._thread.start()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                run_automation_pass(
                    now=datetime.now().astimezone(),
                    automator_factory=lambda project_name: Automator(project_name=project_name),
                )
            except Exception:
                pass
            self._stop_event.wait(self.poll_seconds)


def render_automation_tab(app) -> None:
    store = AutomationStore(project_name=app.generator.ctx.project_name)
    config = store.load_config()
    queue = store.load_queue()
    runtime = store.load_runtime()
    history = store.load_recent_history(limit=10)
    diagnostics_snapshot = build_diagnostics_status_snapshot(
        load_recent_llm_runs(app.generator.ctx.project_name)
    )
    operations_snapshot = build_automation_operations_snapshot(
        config=config,
        queue=queue,
        runtime=runtime,
        history=history,
        diagnostics_snapshot=diagnostics_snapshot,
    )

    st.header("자동화/진단")
    st.caption("스케줄 상태, 자동화 런타임, 대기 작업, 최근 진단 상황을 먼저 확인하고 상세 설정은 아래에서 조정합니다.")

    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
    with summary_col1:
        st.metric("스케줄", operations_snapshot["schedule_summary"])
    with summary_col2:
        st.metric("런타임", operations_snapshot["runtime_status"])
    with summary_col3:
        st.metric("대기 작업", str(operations_snapshot["pending_job_count"]))
    with summary_col4:
        st.metric("최근 진단", diagnostics_snapshot.get("status", "empty"))

    st.divider()
    st.subheader("1. 자동화 상태")
    status_col1, status_col2 = st.columns(2)
    with status_col1:
        st.caption("현재 런타임")
        st.write(f"현재 상태: `{format_runtime_detail_value(runtime.get('status', 'idle'))}`")
        st.write(f"마지막 실행: `{format_runtime_detail_value(runtime.get('last_run_at'))}`")
        st.write(f"현재 작업: `{format_runtime_detail_value(runtime.get('current_job_id'))}`")
        st.write(f"마지막 오류: `{format_runtime_detail_value(runtime.get('last_error'))}`")
    with status_col2:
        st.caption("최근 진단")
        st.write(operations_snapshot["diagnostics_summary"] or "-")
        if diagnostics_snapshot.get("warning_text"):
            st.warning(diagnostics_snapshot["warning_text"])
        else:
            st.info("최근 진단 경고가 없습니다.")

    st.divider()
    st.subheader("2. 주요 경고 / 다음 작업")
    if operations_snapshot["blockers"]:
        for blocker in operations_snapshot["blockers"]:
            st.write(f"- {blocker}")
    else:
        st.info("현재 즉시 대응이 필요한 경고가 없습니다.")
    for action in operations_snapshot["next_actions"]:
        st.write(f"- {action}")

    st.divider()
    st.subheader("3. 작업 큐 / 최근 실행 요약")
    preview_col1, preview_col2 = st.columns(2)
    with preview_col1:
        st.caption("작업 큐")
        if operations_snapshot["queue_rows"]:
            st.dataframe(operations_snapshot["queue_rows"], width="stretch", hide_index=True)
        else:
            st.info("대기 중인 자동화 작업이 없습니다.")
    with preview_col2:
        st.caption("최근 실행")
        history_summary = operations_snapshot["history_summary"]
        st.write(
            f"총 {history_summary['total']}건 / 성공 {history_summary['success']}건 / 실패 {history_summary['failure']}건"
        )
        if operations_snapshot["history_rows"]:
            st.dataframe(operations_snapshot["history_rows"], width="stretch", hide_index=True)
        else:
            st.info("최근 24시간 실행 이력이 없습니다.")

    st.divider()
    st.subheader("4. 고급 설정")
    st.caption("자동화 스케줄, 작업 큐 편집, 런타임 제어, 진단 상세는 아래에서 계속 조정할 수 있습니다.")

    st.subheader("4-1. 스케줄 설정")
    schedule = config.get("schedule", {})
    schedule_type = schedule.get("type", "daily")
    default_time = _parse_time_value(schedule.get("time", "21:00"))
    default_days = [day for day in schedule.get("days", []) if day in WEEKDAY_OPTIONS]
    default_hours = int(schedule.get("hours", 24))
    generation_options = config.get("generation_options", {})
    default_use_plot = bool(generation_options.get("include_plot", False))
    default_plot_strength = str(generation_options.get("plot_strength", "balanced") or "balanced")
    if default_plot_strength not in {"loose", "balanced", "strict"}:
        default_plot_strength = "balanced"
    saved_plot_outline = app.generator.ctx.get_plot_outline()

    enabled = st.checkbox("자동화 활성화", value=config.get("enabled", False), key="automation_enabled")

    auto_use_plot = st.checkbox(
        "저장한 대형 플롯을 자동화 생성/검수 흐름에 반영",
        value=default_use_plot,
        key="automation_use_plot",
        disabled=not bool(saved_plot_outline),
    )
    st.selectbox(
        "플롯 반영 강도",
        options=["loose", "balanced", "strict"],
        index=["loose", "balanced", "strict"].index(default_plot_strength),
        key="automation_plot_strength",
        disabled=not auto_use_plot,
        help="loose: 참고만 / balanced: 권장 / strict: 플롯 우선",
    )
    if not saved_plot_outline:
        st.caption("저장한 플롯이 없어 플롯 반영 옵션은 비활성화되어 있습니다. [1] 프로젝트 통합 설정 > 대형 플롯에서 먼저 생성해 주세요.")

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
        key="automation_schedule_type",
    )
    editor_state = build_schedule_editor_state(selected_type)
    selected_time = default_time
    selected_days: list[str] = default_days
    interval_hours = default_hours
    if editor_state["show_time"]:
        selected_time = st.time_input("실행 시각", value=default_time, step=60, key="automation_schedule_time")
    if editor_state["show_days"]:
        selected_days = st.multiselect(
            "실행 요일",
            options=list(WEEKDAY_OPTIONS),
            default=default_days,
            format_func=lambda value: WEEKDAY_LABELS[value],
            key="automation_schedule_days",
        )
    if editor_state["show_hours"]:
        interval_hours = int(
            st.number_input(
                "반복 간격(시간)",
                min_value=1,
                max_value=168,
                value=default_hours,
                step=1,
                key="automation_interval_hours",
            )
        )

    if st.button("스케줄 저장", type="primary", width="stretch"):
        updated_schedule = {
            "type": selected_type,
            "time": selected_time.strftime("%H:%M"),
            "days": selected_days,
            "hours": interval_hours,
        }
        config["enabled"] = enabled
        config["schedule"] = updated_schedule
        config["context_updates"] = {
            "state": False,
            "summary": False,
        }
        config["generation_options"] = {
            "include_plot": st.session_state.get("automation_use_plot", default_use_plot),
            "plot_strength": st.session_state.get("automation_plot_strength", default_plot_strength),
        }
        store.save_config(config)
        st.success("자동화 스케줄을 저장했습니다.")
        st.rerun()

    st.divider()
    st.subheader("4-2. 작업 큐")
    with st.form("automation_queue_add_form"):
        job_title = st.text_input("회차 제목", value="", key="automation_job_title")
        job_instruction = st.text_area("지시사항", value="", height=160, key="automation_job_instruction")
        job_target_length = int(
            st.number_input(
                "목표 분량",
                min_value=500,
                max_value=20000,
                value=5000,
                step=500,
                key="automation_job_target_length",
            )
        )
        if st.form_submit_button("큐에 추가", type="primary", width="stretch"):
            if not job_title.strip() or not job_instruction.strip():
                st.warning("회차 제목과 지시사항을 모두 입력해 주세요.")
            else:
                queue.append(
                    {
                        "id": f"job_{uuid4().hex[:10]}",
                        "title": job_title.strip(),
                        "instruction": job_instruction.strip(),
                        "target_length": job_target_length,
                        "status": "pending",
                        "attempt_count": 0,
                        "created_at": datetime.now().astimezone().isoformat(),
                        "last_error": "",
                    }
                )
                store.save_queue(queue)
                st.success("작업을 큐에 추가했습니다.")
                st.rerun()

    queue_rows = build_queue_rows(queue)
    if queue_rows:
        st.dataframe(queue_rows, width="stretch", hide_index=True)
        selected_job_id = st.selectbox(
            "작업 선택",
            options=[job.get("id", "") for job in queue],
            format_func=lambda job_id: _format_job_option(queue, job_id),
            key="automation_selected_job_id",
        )
        action_col1, action_col2, action_col3, action_col4 = st.columns(4)
        with action_col1:
            if st.button("위로 이동", width="stretch"):
                _move_job(queue, selected_job_id, direction=-1)
                store.save_queue(queue)
                st.rerun()
        with action_col2:
            if st.button("아래로 이동", width="stretch"):
                _move_job(queue, selected_job_id, direction=1)
                store.save_queue(queue)
                st.rerun()
        with action_col3:
            if st.button("재시도 가능 상태로 초기화", width="stretch"):
                _reset_job(queue, selected_job_id)
                store.save_queue(queue)
                st.rerun()
        with action_col4:
            if st.button("큐에서 제거", width="stretch"):
                updated_queue = [job for job in queue if job.get("id") != selected_job_id]
                store.save_queue(updated_queue)
                st.rerun()
    else:
        st.info("아직 등록된 자동화 작업이 없습니다.")

    st.divider()
    st.subheader("4-3. 런타임 상태")
    status_col1, status_col2 = st.columns(2)
    with status_col1:
        st.write(f"현재 상태: `{runtime.get('status', 'idle')}`")
        st.write(f"마지막 실행: `{format_runtime_detail_value(runtime.get('last_run_at'))}`")
    with status_col2:
        st.write(f"현재 작업: `{format_runtime_detail_value(runtime.get('current_job_id'))}`")
        st.write(f"마지막 오류: `{format_runtime_detail_value(runtime.get('last_error'))}`")

    runtime_action_col1, runtime_action_col2 = st.columns(2)
    with runtime_action_col1:
        if st.button("지금 한 번 체크 실행", width="stretch"):
            runtime_runner = AutomationRuntime(
                store=store,
                automator=Automator(project_name=app.generator.ctx.project_name),
            )
            runtime_runner.tick(now=datetime.now().astimezone())
            st.success("자동화 체크를 한 번 실행했습니다.")
            st.rerun()
    with runtime_action_col2:
        if st.button("paused 해제", width="stretch"):
            store.save_runtime(
                {
                    "status": "idle",
                    "current_job_id": None,
                    "last_run_at": runtime.get("last_run_at"),
                    "last_error": "",
                }
            )
            st.success("자동화 상태를 다시 대기 중으로 돌렸습니다.")
            st.rerun()

    st.divider()
    st.subheader("4-4. 최근 실행 이력")
    history_summary = build_history_summary(history)
    history_col1, history_col2, history_col3 = st.columns(3)
    with history_col1:
        st.metric("24시간 실행", str(history_summary["total"]))
    with history_col2:
        st.metric("성공", str(history_summary["success"]))
    with history_col3:
        st.metric("실패", str(history_summary["failure"]))

    history_rows = build_history_rows(history)
    if history_rows:
        st.dataframe(history_rows, width="stretch", hide_index=True)
    else:
        st.info("최근 24시간 실행 이력이 없습니다.")

    st.divider()
    st.subheader("4-5. 진단 상세")
    render_diagnostics_panel(app.generator.ctx.project_name, key_prefix="automation_diag")


def _parse_time_value(raw_time: str) -> dt_time:
    hour_text, minute_text = raw_time.split(":", maxsplit=1)
    return dt_time(hour=int(hour_text), minute=int(minute_text))


def _format_job_option(queue: list[dict], job_id: str) -> str:
    for index, job in enumerate(queue, start=1):
        if job.get("id") == job_id:
            return f"{index}. {job.get('title', '')} [{job.get('status', 'pending')}]"
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
            return
