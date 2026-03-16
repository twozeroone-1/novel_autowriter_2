from __future__ import annotations

import streamlit as st

from core.platform_credentials import load_platform_credentials
from core.publishing_store import PublishingStore
from ui.publishing import (
    PLATFORM_LABELS,
    count_pending_publishing_jobs,
    format_publishing_runtime_status,
    format_publishing_schedule_summary,
)


REQUIRED_WORKSPACE_FIELDS = ("worldview", "tone_and_manner", "continuity", "state")


def build_operations_overview_snapshot(
    *,
    project_name: str,
    workspace_settings: dict,
    publishing_config: dict,
    publishing_runtime: dict,
    publishing_queue: list[dict],
    credential_loader=load_platform_credentials,
) -> dict:
    settings_ready_count = sum(
        1 for key in REQUIRED_WORKSPACE_FIELDS if str(workspace_settings.get(key, "")).strip()
    )

    platform_rows: list[dict] = []
    blockers: list[str] = []
    enabled_platform_count = 0
    ready_platform_count = 0

    for platform_name, platform_label in PLATFORM_LABELS.items():
        platform_config = publishing_config.get("platforms", {}).get(platform_name, {})
        enabled = bool(platform_config.get("enabled", False))
        has_credentials = False
        has_work_id = bool(str(platform_config.get("work_id", "")).strip())
        has_upload_url_template = bool(str(platform_config.get("upload_url_template", "")).strip())

        if enabled:
            enabled_platform_count += 1
            credentials = credential_loader(project_name, platform_name)
            has_credentials = bool(
                str(credentials.get("username", "")).strip() and str(credentials.get("password", "")).strip()
            )

            if not has_credentials:
                blockers.append(f"{platform_label} 계정이 설정되지 않았습니다.")
            if not has_work_id:
                blockers.append(f"{platform_label} work_id가 비어 있습니다.")
            if not has_upload_url_template:
                blockers.append(f"{platform_label} 업로드 URL이 비어 있습니다.")
            if has_credentials and has_work_id and has_upload_url_template:
                ready_platform_count += 1

        platform_rows.append(
            {
                "platform_name": platform_name,
                "platform_label": platform_label,
                "enabled": enabled,
                "has_credentials": has_credentials,
                "has_work_id": has_work_id,
                "has_upload_url_template": has_upload_url_template,
            }
        )

    if enabled_platform_count == 0:
        blockers.append("활성화된 업로드 플랫폼이 없습니다.")

    runtime_status = str(publishing_runtime.get("status", "idle")).strip().lower() or "idle"
    runtime_status_text = format_publishing_runtime_status(publishing_runtime)
    last_error = str(publishing_runtime.get("last_error", "")).strip()
    if runtime_status in {"blocked", "paused", "stopped"}:
        blockers.append(
            f"발행 런타임 상태를 확인하세요: {runtime_status_text}"
            if not last_error
            else f"발행 런타임 상태를 확인하세요: {runtime_status_text} ({last_error})"
        )

    publishing_ready = enabled_platform_count > 0 and ready_platform_count == enabled_platform_count
    next_actions = _build_next_actions(
        settings_ready_count=settings_ready_count,
        enabled_platform_count=enabled_platform_count,
        platform_rows=platform_rows,
        publishing_ready=publishing_ready,
        pending_job_count=count_pending_publishing_jobs(publishing_queue),
        runtime_status=runtime_status,
    )

    return {
        "project_name": project_name,
        "settings_ready_count": settings_ready_count,
        "settings_total_count": len(REQUIRED_WORKSPACE_FIELDS),
        "settings_ready": settings_ready_count == len(REQUIRED_WORKSPACE_FIELDS),
        "publishing_ready": publishing_ready,
        "enabled_platform_count": enabled_platform_count,
        "ready_platform_count": ready_platform_count,
        "pending_job_count": count_pending_publishing_jobs(publishing_queue),
        "runtime_status": runtime_status,
        "runtime_status_text": runtime_status_text,
        "schedule_summary": format_publishing_schedule_summary(publishing_config),
        "blockers": tuple(_dedupe_preserving_order(blockers)),
        "next_actions": tuple(next_actions),
        "platform_rows": tuple(platform_rows),
    }


def render_operations_overview(app) -> None:
    project_name = app.generator.ctx.project_name
    workspace_settings = app.generator.ctx.get_workspace_settings()
    store = PublishingStore(project_name=project_name)
    publishing_config = store.load_config()
    publishing_runtime = store.load_runtime()
    publishing_queue = store.load_queue()

    snapshot = build_operations_overview_snapshot(
        project_name=project_name,
        workspace_settings=workspace_settings,
        publishing_config=publishing_config,
        publishing_runtime=publishing_runtime,
        publishing_queue=publishing_queue,
    )

    st.header("운영 개요")
    st.caption("작품의 현재 준비 상태, 발행 차단 요인, 다음 권장 작업을 한 화면에서 확인합니다.")

    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
    with summary_col1:
        st.metric("설정 준비도", f"{snapshot['settings_ready_count']}/{snapshot['settings_total_count']}")
    with summary_col2:
        st.metric("발행 준비도", f"{snapshot['ready_platform_count']}/{snapshot['enabled_platform_count']}")
    with summary_col3:
        st.metric("현재 상태", snapshot["runtime_status_text"])
    with summary_col4:
        st.metric("대기 작업", str(snapshot["pending_job_count"]))

    st.divider()
    st.subheader("플랫폼 준비 상태")
    for row in snapshot["platform_rows"]:
        if not row["enabled"]:
            st.caption(f"- {row['platform_label']}: 비활성")
            continue
        status_bits = [
            "계정" if row["has_credentials"] else "계정 없음",
            "work_id" if row["has_work_id"] else "work_id 없음",
            "업로드 URL" if row["has_upload_url_template"] else "업로드 URL 없음",
        ]
        st.caption(f"- {row['platform_label']}: {', '.join(status_bits)}")

    st.divider()
    st.subheader("주요 경고 / 차단 사유")
    if snapshot["blockers"]:
        for blocker in snapshot["blockers"]:
            st.markdown(f"- {blocker}")
    else:
        st.info("현재 확인된 차단 사유가 없습니다.")

    st.divider()
    st.subheader("다음 권장 작업")
    for action in snapshot["next_actions"]:
        st.markdown(f"- {action}")


def _build_next_actions(
    *,
    settings_ready_count: int,
    enabled_platform_count: int,
    platform_rows: list[dict],
    publishing_ready: bool,
    pending_job_count: int,
    runtime_status: str,
) -> list[str]:
    next_actions: list[str] = []

    if settings_ready_count < len(REQUIRED_WORKSPACE_FIELDS):
        next_actions.append("프로젝트 통합 설정에서 STORY_BIBLE / STATE 핵심 문서를 채우세요.")

    if enabled_platform_count == 0:
        next_actions.append("외부 플랫폼 업로드에서 업로드 플랫폼을 활성화하세요.")

    if any(row["enabled"] and not row["has_credentials"] for row in platform_rows):
        next_actions.append("플랫폼 계정을 keyring 또는 env fallback으로 설정하세요.")

    if any(
        row["enabled"] and (not row["has_work_id"] or not row["has_upload_url_template"])
        for row in platform_rows
    ):
        next_actions.append("플랫폼 작품 매핑(work_id / 업로드 URL)을 채우세요.")

    if publishing_ready and pending_job_count <= 0:
        next_actions.append("업로드 큐에 발행할 회차를 추가하세요.")

    if publishing_ready and pending_job_count > 0:
        next_actions.append("외부 플랫폼 업로드에서 smoke 또는 1회 실행을 점검하세요.")

    if runtime_status in {"blocked", "paused", "stopped"}:
        next_actions.append("발행 런타임 상태와 마지막 오류를 확인하세요.")

    if not next_actions:
        next_actions.append("현재 상태는 안정적입니다. 다음 회차 워크플로를 진행하세요.")

    return _dedupe_preserving_order(next_actions)


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
