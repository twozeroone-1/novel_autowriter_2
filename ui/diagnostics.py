import streamlit as st

from core.automation_store import AutomationStore
from core.diagnostics import build_recent_summary, load_recent_llm_runs


RESULT_FILTER_LABELS = {
    "all": "전체",
    "success": "성공",
    "failed": "실패",
}


def format_sidebar_summary(summary: dict) -> str:
    latest_backend = summary.get("latest_backend") or "-"
    return f"24시간 {summary.get('run_count', 0)}건 / 실패 {summary.get('failure_count', 0)}건 / 최근 {latest_backend}"


def build_diagnostics_status_snapshot(records: list[dict]) -> dict[str, str]:
    summary = build_recent_summary(records)
    summary_text = format_sidebar_summary(summary)
    run_count = int(summary.get("run_count", 0) or 0)
    failure_count = int(summary.get("failure_count", 0) or 0)

    if run_count <= 0:
        return {
            "status": "empty",
            "summary_text": summary_text,
            "warning_text": "최근 24시간 진단 기록이 없습니다.",
            "recommended_action": "진단 기록이 없으니 진단 상세를 열어 최근 실행 로그를 확인하세요.",
        }

    if failure_count > 0:
        return {
            "status": "warning",
            "summary_text": summary_text,
            "warning_text": f"최근 진단 실패 {failure_count}건이 있습니다.",
            "recommended_action": "진단 상세를 열어 실패 원인과 fallback 흐름을 확인하세요.",
        }

    return {
        "status": "healthy",
        "summary_text": summary_text,
        "warning_text": "",
        "recommended_action": "최근 진단은 안정적입니다.",
    }


def filter_runs(
    runs: list[dict],
    *,
    success_filter: str = "all",
    requested_backend: str = "all",
    actual_backend: str = "all",
    model_name: str = "all",
) -> list[dict]:
    filtered: list[dict] = []
    for run in runs:
        if success_filter == "failed" and run.get("success", False):
            continue
        if success_filter == "success" and not run.get("success", False):
            continue
        if requested_backend != "all" and run.get("requested_backend") != requested_backend:
            continue
        if actual_backend != "all" and run.get("actual_backend") != actual_backend:
            continue
        if model_name != "all" and run.get("model") != model_name:
            continue
        filtered.append(run)
    return filtered


def build_detail_rows(records: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for record in records:
        rows.append(
            {
                **record,
                "status": "success" if record.get("success") else "failed",
            }
        )
    return rows


def format_automation_context_update(context_update: dict) -> str:
    if not isinstance(context_update, dict):
        return "-"

    legacy = context_update.get("legacy", {}) if isinstance(context_update.get("legacy"), dict) else {}
    canon_candidate = (
        context_update.get("canon_candidate", {}) if isinstance(context_update.get("canon_candidate"), dict) else {}
    )
    parts: list[str] = []
    legacy_status = str(legacy.get("status", "")).strip()
    canon_status = str(canon_candidate.get("status", "")).strip()
    if legacy_status:
        parts.append(f"legacy: {legacy_status}")
    if canon_status:
        parts.append(f"canon: {canon_status}")
    if parts:
        return " / ".join(parts)

    fallback = str(context_update.get("status", "")).strip()
    return fallback or "-"


def build_automation_history_rows(records: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for record in records:
        context_update = record.get("context_update", {}) or {}
        rows.append(
            {
                "timestamp": record.get("timestamp", ""),
                "title": record.get("title", ""),
                "result": "success" if record.get("success") else "failed",
                "context_update": format_automation_context_update(context_update),
                "detail": record.get("saved_path", "") if record.get("success") else record.get("error_text", ""),
            }
        )
    return rows


def get_diagnostics_warning_text() -> str:
    return "이 화면에는 민감한 프롬프트와 응답 원문이 포함될 수 있습니다. 필요한 경우에만 상세 원문을 펼쳐서 확인해 주세요."


def get_sidebar_summary(project_name: str) -> dict:
    return build_recent_summary(load_recent_llm_runs(project_name))


def _panel_key(key_prefix: str, suffix: str) -> str:
    return f"{key_prefix}_{suffix}"


def render_detail_fields(row: dict, *, index: int, key_prefix: str = "diag") -> None:
    st.text_area(
        "프롬프트",
        value=row.get("prompt_text", ""),
        height=160,
        key=_panel_key(key_prefix, f"prompt_{index}"),
        disabled=True,
    )
    st.text_area(
        "응답",
        value=row.get("response_text", ""),
        height=160,
        key=_panel_key(key_prefix, f"response_{index}"),
        disabled=True,
    )
    st.text_area(
        "stderr",
        value=row.get("stderr_text", ""),
        height=100,
        key=_panel_key(key_prefix, f"stderr_{index}"),
        disabled=True,
    )
    st.text_area(
        "오류",
        value=row.get("error_text", ""),
        height=100,
        key=_panel_key(key_prefix, f"error_{index}"),
        disabled=True,
    )
    st.text_area(
        "fallback 메모",
        value=row.get("fallback_note", ""),
        height=80,
        key=_panel_key(key_prefix, f"fallback_{index}"),
        disabled=True,
    )


def render_diagnostics_panel(project_name: str, *, key_prefix: str = "diag") -> None:
    records = load_recent_llm_runs(project_name)
    summary = build_recent_summary(records)
    automation_history = AutomationStore(project_name=project_name).load_recent_history(limit=10)

    with st.expander("고급: 진단 / 실행 기록", expanded=False):
        st.warning(get_diagnostics_warning_text())
        st.caption(format_sidebar_summary(summary))

        success_filter = st.selectbox(
            "결과",
            ["all", "success", "failed"],
            key=_panel_key(key_prefix, "success_filter"),
            format_func=lambda item: RESULT_FILTER_LABELS[item],
        )
        requested_backend = st.selectbox(
            "요청 백엔드",
            ["all"] + sorted({record.get("requested_backend") for record in records if record.get("requested_backend")}),
            key=_panel_key(key_prefix, "requested_backend"),
            format_func=lambda item: "전체" if item == "all" else item,
        )
        actual_backend = st.selectbox(
            "실제 백엔드",
            ["all"] + sorted({record.get("actual_backend") for record in records if record.get("actual_backend")}),
            key=_panel_key(key_prefix, "actual_backend"),
            format_func=lambda item: "전체" if item == "all" else item,
        )
        model_name = st.selectbox(
            "모델",
            ["all"] + sorted({record.get("model") for record in records if record.get("model")}),
            key=_panel_key(key_prefix, "model_name"),
            format_func=lambda item: "전체" if item == "all" else item,
        )

        filtered_records = filter_runs(
            records,
            success_filter=success_filter,
            requested_backend=requested_backend,
            actual_backend=actual_backend,
            model_name=model_name,
        )

        if not filtered_records:
            st.caption("최근 24시간 기록이 없습니다.")
            pass

        for index, row in enumerate(build_detail_rows(filtered_records)):
            label = (
                f"{row.get('timestamp', '-')}"
                f" | {row.get('feature', '-')}"
                f" | {row.get('status', '-')}"
                f" | {row.get('actual_backend', '-')}"
                f" | {row.get('model', '-')}"
                f" | {row.get('duration_ms', 0)} ms"
            )
            with st.expander(label, expanded=False):
                render_detail_fields(row, index=index, key_prefix=key_prefix)

        st.divider()
        st.caption("자동화 연재 실행 기록")
        if automation_history:
            st.dataframe(
                build_automation_history_rows(automation_history),
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("저장된 자동화 실행 기록이 없습니다.")
