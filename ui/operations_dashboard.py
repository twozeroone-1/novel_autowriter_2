from __future__ import annotations

import streamlit as st

from core.episode_artifact_store import EpisodeArtifactStore
from core.platform_credentials import load_platform_credentials
from core.publishing_readiness import build_publishing_readiness_snapshot
from core.publishing_store import PublishingStore
from core.run_snapshot_store import RunSnapshotStore
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
    latest_episode_plan: dict | None = None,
    latest_episode: dict | None = None,
    latest_quality_report: dict | None = None,
    credential_loader=load_platform_credentials,
) -> dict:
    settings_ready_count = sum(
        1 for key in REQUIRED_WORKSPACE_FIELDS if str(workspace_settings.get(key, "")).strip()
    )

    readiness_snapshot = build_publishing_readiness_snapshot(
        project_name=project_name,
        config=publishing_config,
        credential_loader=credential_loader,
    )
    platform_rows = list(readiness_snapshot["platform_rows"])
    blockers: list[str] = list(readiness_snapshot["blockers"])
    enabled_platform_count = int(readiness_snapshot["enabled_platform_count"])
    ready_platform_count = int(readiness_snapshot["ready_platform_count"])

    runtime_status = str(publishing_runtime.get("status", "idle")).strip().lower() or "idle"
    runtime_status_text = format_publishing_runtime_status(publishing_runtime)
    last_error = str(publishing_runtime.get("last_error", "")).strip()
    if runtime_status in {"blocked", "paused", "stopped"}:
        blockers.append(
            f"발행 런타임 상태를 확인하세요: {runtime_status_text}"
            if not last_error
            else f"발행 런타임 상태를 확인하세요: {runtime_status_text} ({last_error})"
        )

    publishing_ready = bool(readiness_snapshot["publishing_ready"])
    next_actions = _build_next_actions(
        settings_ready_count=settings_ready_count,
        readiness_actions=list(readiness_snapshot["recommended_actions"]),
        publishing_ready=publishing_ready,
        pending_job_count=count_pending_publishing_jobs(publishing_queue),
        runtime_status=runtime_status,
    )
    timeline_steps = _build_timeline_steps(
        settings_ready_count=settings_ready_count,
        latest_episode_plan=latest_episode_plan or {},
        latest_episode=latest_episode or {},
        latest_quality_report=latest_quality_report or {},
        publishing_queue=publishing_queue,
        publishing_runtime=publishing_runtime,
    )
    shortcut_actions = _build_shortcut_actions(
        settings_ready_count=settings_ready_count,
        runtime_status=runtime_status,
        publishing_ready=publishing_ready,
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
        "timeline_steps": tuple(timeline_steps),
        "shortcut_actions": tuple(shortcut_actions),
        "platform_rows": tuple(platform_rows),
    }


def render_operations_overview(app, *, navigate_to_tab=None) -> None:
    project_name = app.generator.ctx.project_name
    workspace_settings = app.generator.ctx.get_workspace_settings()
    store = PublishingStore(project_name=project_name)
    artifact_store = EpisodeArtifactStore(project_name=project_name)
    snapshot_store = RunSnapshotStore(project_name=project_name)
    publishing_config = store.load_config()
    publishing_runtime = store.load_runtime()
    publishing_queue = store.load_queue()
    latest_episode_plan = _load_latest_run_json(snapshot_store.runs_dir, "chapter_", "episode_plan.json")
    latest_quality_report = _load_latest_run_json(snapshot_store.runs_dir, "origin_", "quality_report.json")
    latest_episode = _select_latest_episode(artifact_store.load_manifest())

    snapshot = build_operations_overview_snapshot(
        project_name=project_name,
        workspace_settings=workspace_settings,
        publishing_config=publishing_config,
        publishing_runtime=publishing_runtime,
        publishing_queue=publishing_queue,
        latest_episode_plan=latest_episode_plan,
        latest_episode=latest_episode,
        latest_quality_report=latest_quality_report,
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

    st.divider()
    st.subheader("오늘의 회차 상태 타임라인")
    timeline_columns = st.columns(len(snapshot["timeline_steps"]))
    for column, step in zip(timeline_columns, snapshot["timeline_steps"]):
        with column:
            st.caption(step["state"])
            st.markdown(f"**{step['label']}**")

    st.divider()
    st.subheader("바로가기 액션")
    _render_shortcut_actions(
        snapshot["shortcut_actions"],
        navigate_to_tab=navigate_to_tab,
        key_prefix="operations_shortcut",
    )


def _build_next_actions(
    *,
    settings_ready_count: int,
    readiness_actions: list[str],
    publishing_ready: bool,
    pending_job_count: int,
    runtime_status: str,
) -> list[str]:
    next_actions: list[str] = []

    if settings_ready_count < len(REQUIRED_WORKSPACE_FIELDS):
        next_actions.append("프로젝트 통합 설정에서 STORY_BIBLE / STATE 핵심 문서를 채우세요.")
    next_actions.extend(readiness_actions)

    if publishing_ready and pending_job_count <= 0:
        next_actions.append("업로드 큐에 발행할 회차를 추가하세요.")

    if publishing_ready and pending_job_count > 0:
        next_actions.append("외부 플랫폼 업로드에서 smoke 또는 1회 실행을 점검하세요.")

    if runtime_status in {"blocked", "paused", "stopped"}:
        next_actions.append("발행 런타임 상태와 마지막 오류를 확인하세요.")

    if not next_actions:
        next_actions.append("현재 상태는 안정적입니다. 다음 회차 워크플로를 진행하세요.")

    return _dedupe_preserving_order(next_actions)


def _build_timeline_steps(
    *,
    settings_ready_count: int,
    latest_episode_plan: dict,
    latest_episode: dict,
    latest_quality_report: dict,
    publishing_queue: list[dict],
    publishing_runtime: dict,
) -> list[dict]:
    stage_states = ["대기"] * 6
    labels = ("설정", "계획", "생성", "품질", "발행", "후속 검증")

    if settings_ready_count >= len(REQUIRED_WORKSPACE_FIELDS):
        stage_states[0] = "완료"
    else:
        stage_states[0] = "현재"
        return _zip_timeline(labels, stage_states)

    if _has_meaningful_plan(latest_episode_plan):
        stage_states[1] = "완료"
    else:
        stage_states[1] = "현재"
        return _zip_timeline(labels, stage_states)

    if latest_episode:
        stage_states[2] = "완료"
    else:
        stage_states[2] = "현재"
        return _zip_timeline(labels, stage_states)

    quality_status = str((latest_quality_report or {}).get("status", "")).strip().lower()
    if quality_status == "hard_fail":
        stage_states[3] = "차단"
        return _zip_timeline(labels, stage_states)
    if quality_status == "publishable":
        stage_states[3] = "완료"
    else:
        stage_states[3] = "현재"
        return _zip_timeline(labels, stage_states)

    if count_pending_publishing_jobs(publishing_queue) > 0:
        stage_states[4] = "현재"
    else:
        stage_states[4] = "다음"
        return _zip_timeline(labels, stage_states)

    runtime_status = str(publishing_runtime.get("status", "idle")).strip().lower()
    if runtime_status == "scheduled":
        stage_states[5] = "현재"
    else:
        stage_states[5] = "다음"
    return _zip_timeline(labels, stage_states)


def _zip_timeline(labels: tuple[str, ...], states: list[str]) -> list[dict]:
    return [{"label": label, "state": state} for label, state in zip(labels, states)]


def _build_shortcut_actions(
    *,
    settings_ready_count: int,
    runtime_status: str,
    publishing_ready: bool,
) -> list[dict]:
    actions = [
        {
            "label": "프로젝트 통합 설정 열기",
            "description": "STORY_BIBLE, CONTINUITY, STATE 등 핵심 문서를 먼저 점검합니다.",
            "target_tab": "작품 설정",
            "target_subsection": "기본 설정",
        },
        {
            "label": "회차 워크플로 보기",
            "description": "최근 계획, 초안, 품질 게이트, 패키지 상태를 한 번에 확인합니다.",
            "target_tab": "회차 워크플로",
            "target_subsection": None,
        },
        {
            "label": "발행 운영 확인",
            "description": "플랫폼 readiness, 업로드 큐, smoke 결과를 점검합니다.",
            "target_tab": "발행 운영",
            "target_subsection": None,
        },
        {
            "label": "자동화/진단 확인",
            "description": "자동화 런타임과 최근 진단 경고를 확인합니다.",
            "target_tab": "자동화/진단",
            "target_subsection": None,
        },
    ]
    if settings_ready_count < len(REQUIRED_WORKSPACE_FIELDS):
        return actions
    if runtime_status in {"blocked", "paused", "stopped"} or not publishing_ready:
        return actions
    return actions


def _render_shortcut_actions(shortcut_actions: tuple[dict, ...], *, navigate_to_tab=None, key_prefix: str) -> None:
    for index, action in enumerate(shortcut_actions):
        if callable(navigate_to_tab):
            if st.button(action["label"], key=f"{key_prefix}_{index}", width="stretch"):
                navigate_to_tab(action["target_tab"], subsection=action.get("target_subsection"))
            st.caption(action["description"])
            continue

        st.markdown(f"- **{action['label']}**: {action['description']}")


def _has_meaningful_plan(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    if str(payload.get("episode_objective", "")).strip():
        return True
    for field in (
        "must_include_characters",
        "hooks_to_payoff",
        "hooks_to_advance",
        "forbidden_moves",
        "continuity_focus",
    ):
        value = payload.get(field, [])
        if isinstance(value, list) and any(str(item).strip() for item in value):
            return True
    return False


def _load_latest_run_json(runs_dir, prefix: str, filename: str) -> dict:
    if not runs_dir.exists():
        return {}
    candidates = sorted(
        (
            path
            for path in runs_dir.iterdir()
            if path.is_dir() and path.name.startswith(prefix) and (path / filename).exists()
        ),
        key=lambda path: path.name,
        reverse=True,
    )
    if not candidates:
        return {}
    target = candidates[0] / filename
    try:
        import json

        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _select_latest_episode(manifest: dict) -> dict:
    episodes = manifest.get("episodes", {}) if isinstance(manifest, dict) else {}
    candidates = [payload for payload in episodes.values() if isinstance(payload, dict)]
    if not candidates:
        return {}
    return max(
        candidates,
        key=lambda payload: (
            int(payload.get("sequence", 0) or 0),
            str(payload.get("episode_id", "")),
        ),
    )


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
