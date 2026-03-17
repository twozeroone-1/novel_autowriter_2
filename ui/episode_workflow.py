from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from core.app_paths import DATA_PROJECTS_DIR
from core.episode_artifact_store import EpisodeArtifactStore
from core.publishing_store import PublishingStore
from core.run_snapshot_store import RunSnapshotStore
from ui.publishing import count_pending_publishing_jobs


WORKFLOW_STAGE_LABELS = ("계획", "초안", "품질 게이트", "발행 패키지")


def build_episode_workflow_snapshot(
    *,
    manifest: dict,
    latest_episode_content: str,
    latest_episode_plan: dict,
    latest_quality_report: dict,
    latest_packager_report: dict,
    publishing_queue: list[dict],
    publishing_history: list[dict],
) -> dict:
    latest_episode = _select_latest_episode(manifest)
    plan_ready = _has_meaningful_plan(latest_episode_plan)
    quality_status = str(latest_quality_report.get("status", "")).strip().lower()
    package_count = len((latest_packager_report.get("packages") or {})) if isinstance(latest_packager_report, dict) else 0
    queue_link = _build_queue_link_snapshot(latest_episode, publishing_queue)
    quality_flags = _extract_quality_flags(latest_quality_report)

    steps = (
        {
            "label": WORKFLOW_STAGE_LABELS[0],
            "state": "완료" if plan_ready else "대기",
            "summary": _build_plan_summary(latest_episode_plan),
        },
        {
            "label": WORKFLOW_STAGE_LABELS[1],
            "state": "완료" if latest_episode else "차단",
            "summary": _build_draft_summary(latest_episode),
        },
        {
            "label": WORKFLOW_STAGE_LABELS[2],
            "state": _build_quality_state(quality_status),
            "summary": _build_quality_summary(latest_quality_report),
        },
        {
            "label": WORKFLOW_STAGE_LABELS[3],
            "state": _build_packager_state(package_count=package_count, quality_status=quality_status),
            "summary": _build_packager_summary(latest_packager_report, queue_link_summary=queue_link["summary"]),
        },
    )

    next_actions = _build_next_actions(
        latest_episode=latest_episode,
        quality_status=quality_status,
        package_count=package_count,
        pending_job_count=count_pending_publishing_jobs(publishing_queue),
        history_count=len(publishing_history),
    )
    shortcut_actions = _build_shortcut_actions(
        latest_episode=latest_episode,
        quality_status=quality_status,
        package_count=package_count,
        pending_job_count=count_pending_publishing_jobs(publishing_queue),
    )

    summary_lines = _dedupe_preserving_order(
        [
            _build_episode_headline(latest_episode),
            _build_plan_summary(latest_episode_plan),
            _build_quality_summary(latest_quality_report),
            _build_packager_summary(latest_packager_report, queue_link_summary=queue_link["summary"]),
            f"대기 중인 업로드 작업 {count_pending_publishing_jobs(publishing_queue)}건",
            f"최근 발행 이력 {len(publishing_history)}건",
        ]
    )

    return {
        "episode": latest_episode,
        "steps": steps,
        "summary_lines": tuple(summary_lines),
        "next_actions": tuple(next_actions),
        "shortcut_actions": tuple(shortcut_actions),
        "episode_plan_preview": latest_episode_plan if isinstance(latest_episode_plan, dict) else {},
        "quality_report_preview": latest_quality_report if isinstance(latest_quality_report, dict) else {},
        "packager_report_preview": latest_packager_report if isinstance(latest_packager_report, dict) else {},
        "draft_path": _resolve_episode_display_path(latest_episode),
        "draft_preview": _build_content_preview(latest_episode_content),
        "quality_summary": _build_quality_summary(latest_quality_report),
        "critic_status": quality_flags["critic_status"],
        "repair_applied": quality_flags["repair_applied"],
        "regenerate_applied": quality_flags["regenerate_applied"],
        "queue_linked": queue_link["linked"],
        "queue_link_summary": queue_link["summary"],
        "packager_summary": _build_packager_summary(latest_packager_report, queue_link_summary=queue_link["summary"]),
    }


def render_episode_workflow(app, *, navigate_to_tab=None) -> None:
    project_name = app.generator.ctx.project_name
    context = load_episode_workflow_context(project_name)
    snapshot = build_episode_workflow_snapshot(**context)

    st.header("회차 워크플로")
    st.caption("최근 실행 기준으로 계획 -> 초안 -> 품질 게이트 -> 발행 패키지 흐름을 보여줍니다.")

    step_columns = st.columns(len(snapshot["steps"]))
    for column, step in zip(step_columns, snapshot["steps"]):
        with column:
            st.caption(step["state"])
            st.markdown(f"**{step['label']}**")
            st.caption(step["summary"])

    st.divider()
    left_col, right_col = st.columns((1, 1))
    with left_col:
        st.subheader("현재 단계 요약")
        for line in snapshot["summary_lines"]:
            st.markdown(f"- {line}")

        st.subheader("다음 권장 작업")
        for action in snapshot["next_actions"]:
            st.markdown(f"- {action}")

        st.subheader("바로가기 액션")
        _render_shortcut_actions(
            snapshot["shortcut_actions"],
            navigate_to_tab=navigate_to_tab,
            key_prefix="episode_workflow_shortcut",
        )

    with right_col:
        st.subheader("단계 상세")
        _render_detail_list(
            "최근 초안",
            [
                f"경로: {snapshot['draft_path'] or '-'}",
                f"요약: {snapshot['draft_preview']}",
            ],
        )
        _render_detail_list(
            "품질 게이트",
            [
                f"상태: {snapshot['quality_summary']}",
                f"critic: {snapshot['critic_status'] or '-'}",
                f"repair: {'적용' if snapshot['repair_applied'] else '없음'}",
                f"regenerate: {'적용' if snapshot['regenerate_applied'] else '없음'}",
            ],
        )
        _render_detail_list(
            "발행 패키지",
            [
                f"패키지: {snapshot['packager_summary']}",
                f"큐 연결: {snapshot['queue_link_summary']}",
            ],
        )
        _render_json_preview("episode_plan.json", snapshot["episode_plan_preview"])
        _render_json_preview("quality_report.json", snapshot["quality_report_preview"])
        _render_json_preview("packager_report.json", snapshot["packager_report_preview"])


def load_episode_workflow_context(project_name: str) -> dict:
    artifact_store = EpisodeArtifactStore(project_name=project_name)
    publishing_store = PublishingStore(project_name=project_name)
    snapshot_store = RunSnapshotStore(project_name=project_name)
    manifest = artifact_store.load_manifest()

    return {
        "manifest": manifest,
        "latest_episode_content": _load_latest_episode_content(project_name, manifest),
        "latest_episode_plan": _load_latest_run_json(snapshot_store.runs_dir, "chapter_", "episode_plan.json"),
        "latest_quality_report": _load_latest_run_json(snapshot_store.runs_dir, "origin_", "quality_report.json"),
        "latest_packager_report": _load_latest_run_json(snapshot_store.runs_dir, "origin_", "packager_report.json"),
        "publishing_queue": publishing_store.load_queue(),
        "publishing_history": publishing_store.load_recent_history(limit=10),
    }


def _render_json_preview(label: str, payload: dict) -> None:
    with st.expander(label, expanded=False):
        if payload:
            st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")
        else:
            st.info("아직 저장된 스냅샷이 없습니다.")


def _render_detail_list(title: str, lines: list[str]) -> None:
    st.caption(title)
    for line in lines:
        st.markdown(f"- {line}")


def _load_latest_run_json(runs_dir: Path, prefix: str, filename: str) -> dict:
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


def _load_latest_episode_content(project_name: str, manifest: dict) -> str:
    latest_episode = _select_latest_episode(manifest)
    relative_path = _resolve_episode_display_path(latest_episode)
    if not relative_path:
        return ""
    target = DATA_PROJECTS_DIR / project_name / relative_path
    try:
        return target.read_text(encoding="utf-8")
    except OSError:
        return ""


def _resolve_episode_display_path(latest_episode: dict) -> str:
    if not latest_episode:
        return ""
    for field in ("draft_path", "publishable_path", "published_path"):
        value = str(latest_episode.get(field, "")).strip()
        if value:
            return value
    return ""


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


def _build_episode_headline(latest_episode: dict) -> str:
    if not latest_episode:
        return "최근 초안이 없습니다."
    return (
        f"최근 회차 {latest_episode.get('episode_id', '')}: "
        f"{latest_episode.get('title', '')} ({latest_episode.get('status', '')})"
    ).strip()


def _build_plan_summary(payload: dict) -> str:
    if not _has_meaningful_plan(payload):
        return "최근 계획 스냅샷이 없습니다."
    objective = str(payload.get("episode_objective", "")).strip()
    target_length = payload.get("target_length")
    characters = payload.get("must_include_characters", [])
    bits = []
    if objective:
        bits.append(objective)
    if characters:
        bits.append(f"등장인물 {len(characters)}명")
    if target_length:
        bits.append(f"목표 분량 {target_length}자")
    return " / ".join(bits)


def _build_draft_summary(latest_episode: dict) -> str:
    if not latest_episode:
        return "초안이 아직 저장되지 않았습니다."
    return f"{latest_episode.get('title', '')} / {latest_episode.get('status', '')}"


def _build_content_preview(content: str, *, limit: int = 180) -> str:
    normalized_lines: list[str] = []
    for raw_line in str(content or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        normalized_lines.append(line)
    if not normalized_lines:
        return "아직 저장된 초안 본문이 없습니다."
    preview = " ".join(normalized_lines)
    if len(preview) <= limit:
        return preview
    return f"{preview[:limit - 3].rstrip()}..."


def _build_quality_state(quality_status: str) -> str:
    if quality_status == "publishable":
        return "완료"
    if quality_status == "hard_fail":
        return "차단"
    if quality_status:
        return "주의"
    return "대기"


def _build_quality_summary(payload: dict) -> str:
    if not isinstance(payload, dict) or not payload:
        return "최근 품질 게이트 결과가 없습니다."

    status = str(payload.get("status", "")).strip().lower()
    if status == "publishable":
        bits = ["최종 통과"]
        if payload.get("attempted_repair"):
            bits.append("repair 1회 적용")
        if payload.get("attempted_regenerate"):
            bits.append("regenerate 1회 적용")
        critic_status = str(
            (((payload.get("gate_reports") or {}).get("final") or {}).get("critic") or {}).get("status", "")
        ).strip()
        if critic_status:
            bits.append(f"critic {critic_status}")
        return ", ".join(bits)

    if status == "hard_fail":
        errors = payload.get("errors", [])
        error_text = ", ".join(str(item) for item in errors[:3]) if isinstance(errors, list) else ""
        return f"차단됨: {error_text or '상세 사유 확인 필요'}"

    return f"최근 품질 상태: {status or '없음'}"


def _extract_quality_flags(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {
            "critic_status": "",
            "repair_applied": False,
            "regenerate_applied": False,
        }
    critic_status = str(
        (((payload.get("gate_reports") or {}).get("final") or {}).get("critic") or {}).get("status", "")
    ).strip()
    return {
        "critic_status": critic_status,
        "repair_applied": bool(payload.get("attempted_repair")),
        "regenerate_applied": bool(payload.get("attempted_regenerate")),
    }


def _build_packager_state(*, package_count: int, quality_status: str) -> str:
    if package_count > 0:
        return "완료"
    if quality_status == "hard_fail":
        return "대기"
    if quality_status == "publishable":
        return "준비"
    return "대기"


def _build_packager_summary(payload: dict, *, queue_link_summary: str = "") -> str:
    packages = (payload.get("packages") or {}) if isinstance(payload, dict) else {}
    if not isinstance(packages, dict) or not packages:
        return "최근 발행 패키지 스냅샷이 없습니다."
    labels = ", ".join(_platform_label(name) for name in packages.keys())
    if queue_link_summary:
        return f"{labels} 패키지 준비 완료 / {queue_link_summary}"
    return f"{labels} 패키지 준비 완료"


def _platform_label(platform_name: str) -> str:
    return {
        "munpia": "문피아",
        "novelpia": "노벨피아",
    }.get(str(platform_name), str(platform_name))


def _build_queue_link_snapshot(latest_episode: dict, publishing_queue: list[dict]) -> dict:
    if not latest_episode:
        return {"linked": False, "summary": "연결된 업로드 작업이 없습니다."}

    episode_id = str(latest_episode.get("episode_id", "")).strip()
    title = str(latest_episode.get("title", "")).strip()
    matched_jobs = []
    for job in publishing_queue:
        if not isinstance(job, dict):
            continue
        job_status = str(job.get("status", "")).strip()
        if job_status not in {"pending", "partial_failed", "scheduled"}:
            continue
        if episode_id and str(job.get("episode_id", "")).strip() == episode_id:
            matched_jobs.append(job)
            continue
        if title and str(job.get("title", "")).strip() == title:
            matched_jobs.append(job)

    if not matched_jobs:
        return {"linked": False, "summary": "연결된 업로드 작업이 없습니다."}

    platforms = []
    statuses = []
    for job in matched_jobs:
        statuses.append(str(job.get("status", "")).strip())
        targets = job.get("targets", {})
        if isinstance(targets, dict):
            for platform_name, payload in targets.items():
                if isinstance(payload, dict) and payload.get("selected"):
                    platforms.append(_platform_label(platform_name))
    platform_summary = ", ".join(_dedupe_preserving_order(platforms)) or "플랫폼 정보 없음"
    status_summary = ", ".join(_dedupe_preserving_order(statuses))
    return {
        "linked": True,
        "summary": f"큐 연결됨 ({status_summary} / {platform_summary})",
    }


def _build_next_actions(
    *,
    latest_episode: dict,
    quality_status: str,
    package_count: int,
    pending_job_count: int,
    history_count: int,
) -> list[str]:
    actions: list[str] = []

    if not latest_episode:
        actions.append("고급: 회차 생성에서 새 초안을 만들고 저장하세요.")
        return actions

    if quality_status == "hard_fail":
        actions.append("고급: 원고 검수에서 품질 차단 사유를 먼저 해결하세요.")
    elif not quality_status:
        actions.append("발행 운영에서 품질 게이트를 먼저 통과시키세요.")
    elif quality_status == "publishable" and package_count == 0:
        actions.append("외부 플랫폼 업로드에서 업로드 큐를 추가해 발행 패키지를 만드세요.")

    if package_count > 0 and pending_job_count > 0:
        actions.append("발행 운영에서 대기 중인 업로드 작업과 플랫폼 상태를 확인하세요.")

    if history_count <= 0:
        actions.append("최근 발행 이력이 없으니 smoke 또는 수동 발행 점검을 먼저 수행하세요.")

    if not actions:
        actions.append("최근 회차 워크플로는 안정적입니다. 다음 회차 계획을 준비하세요.")

    return _dedupe_preserving_order(actions)


def _build_shortcut_actions(
    *,
    latest_episode: dict,
    quality_status: str,
    package_count: int,
    pending_job_count: int,
) -> list[dict]:
    if not latest_episode:
        return [
            {
                "label": "고급: 회차 생성 열기",
                "description": "새 초안을 만들고 최근 회차 아티팩트를 생성합니다.",
                "target_tab": "고급: 회차 생성",
                "target_subsection": None,
            },
            {
                "label": "작품 설정 열기",
                "description": "STORY_BIBLE과 STATE가 비어 있지 않은지 먼저 확인합니다.",
                "target_tab": "작품 설정",
                "target_subsection": "기본 설정",
            },
        ]

    if quality_status == "hard_fail":
        return [
            {
                "label": "고급: 원고 검수 열기",
                "description": "차단 사유를 보고 수정본을 다시 저장합니다.",
                "target_tab": "고급: 원고 검수",
                "target_subsection": None,
            },
            {
                "label": "고급: 회차 생성 열기",
                "description": "필요하면 초안을 다시 생성하거나 수동으로 보정합니다.",
                "target_tab": "고급: 회차 생성",
                "target_subsection": None,
            },
        ]

    if quality_status == "publishable" and package_count == 0:
        return [
            {
                "label": "발행 운영 열기",
                "description": "업로드 큐를 추가하고 발행 패키지를 준비합니다.",
                "target_tab": "발행 운영",
                "target_subsection": None,
            },
            {
                "label": "자동화/진단 확인",
                "description": "자동 발행 스케줄과 최근 진단 상태를 함께 점검합니다.",
                "target_tab": "자동화/진단",
                "target_subsection": None,
            },
        ]

    if package_count > 0 and pending_job_count > 0:
        return [
            {
                "label": "발행 운영 열기",
                "description": "대기 중인 업로드 작업과 플랫폼 상태를 확인합니다.",
                "target_tab": "발행 운영",
                "target_subsection": None,
            },
            {
                "label": "자동화/진단 확인",
                "description": "scheduled, cooldown, blocked 상태가 없는지 점검합니다.",
                "target_tab": "자동화/진단",
                "target_subsection": None,
            },
        ]

    return [
        {
            "label": "회차 워크플로 유지",
            "description": "현재 흐름은 안정적입니다. 다음 회차 계획을 준비하세요.",
            "target_tab": "회차 워크플로",
            "target_subsection": None,
        },
        {
            "label": "고급: 반자동 실행 열기",
            "description": "필요하면 반자동 파이프라인으로 빠르게 다음 회차를 준비합니다.",
            "target_tab": "고급: 반자동 실행",
            "target_subsection": None,
        },
    ]


def _render_shortcut_actions(shortcut_actions: tuple[dict, ...], *, navigate_to_tab=None, key_prefix: str) -> None:
    for index, action in enumerate(shortcut_actions):
        if callable(navigate_to_tab):
            if st.button(action["label"], key=f"{key_prefix}_{index}", width="stretch"):
                navigate_to_tab(action["target_tab"], subsection=action.get("target_subsection"))
            st.caption(action["description"])
            continue

        st.markdown(f"- **{action['label']}**: {action['description']}")


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
