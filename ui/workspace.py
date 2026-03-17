import json
import os
import re
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

import streamlit as st
from dotenv import load_dotenv

from core.api_key_store import (
    delete_api_key_from_secure_storage,
    env_file_has_key,
    get_secure_api_key,
    has_secure_storage,
    save_api_key_to_secure_storage,
    set_runtime_api_key,
)
from core.app_paths import DATA_PROJECTS_DIR
from core.automation_store import AutomationStore
from core.generator import Generator
from core.llm import LLMError
from core.llm_backend import GeminiCliStatus, probe_gemini_cli, resolve_backend_mode, test_gemini_cli_connection
from core.model_catalog import get_available_models
from core.token_budget import find_latest_sample_chapter, get_budget_recommendations, get_field_stats
from ui.automation import format_runtime_status, format_schedule_summary
from ui.diagnostics import format_sidebar_summary, get_sidebar_summary, render_diagnostics_panel


@dataclass(frozen=True)
class TextAssistAction:
    label: str
    button_key: str
    empty_warning: str
    spinner_text: str
    error_prefix: str
    notice: str
    transform: Callable[[str], str]


@dataclass(frozen=True)
class ProjectFieldSpec:
    section_title: str
    subtitle: str
    guide_text: str
    input_label: str
    config_key: str
    textarea_key: str
    height: int
    actions: tuple[TextAssistAction, ...]


@dataclass(frozen=True)
class ProjectFieldPanel:
    spec: ProjectFieldSpec
    char_count: int
    recommended_max_chars: int
    status: str
    tip: str
    expander_label: str
    preview_text: str
    expanded: bool


@dataclass(frozen=True)
class CanonStoreSummary:
    people_count: int
    resources_count: int
    hooks_count: int
    timeline_count: int


@dataclass(frozen=True)
class ReleasePolicySummary:
    max_daily_releases: int
    burst_allowed: bool
    cooldown_failures: int
    enabled_platforms: tuple[str, ...]


@dataclass(frozen=True)
class ProjectSettingsStatusSnapshot:
    filled_count: int
    attention_count: int
    total_config_chars: int
    previous_summary_status: str
    previous_summary_label: str
    structured_store_label: str
    warnings: tuple[str, ...]
    recommended_actions: tuple[str, ...]


BACKEND_MODE_OPTIONS = {
    "auto": "자동 (CLI 우선, 실패 시 API)",
    "api": "Gemini API만 사용",
    "cli": "Gemini CLI만 사용",
}
STORY_BIBLE_FIELD_KEYS = ("worldview", "tone_and_manner", "continuity")


def format_cli_status(status: GeminiCliStatus) -> str:
    if not status.available:
        return "설치 안 됨"
    if status.authenticated is True:
        return "OAuth 사용 가능"
    if status.authenticated is False:
        return "로그인 필요"
    return "설치됨 · 테스트 필요"


def render_section_header(title: str, subtitle: str, guide_text: str) -> None:
    st.subheader(title)
    subtitle_col, guide_col = st.columns([3, 2])
    with subtitle_col:
        st.caption(subtitle)
    with guide_col:
        st.caption(f"권장 길이: {guide_text}")


def build_project_field_specs(generator: Generator) -> tuple[ProjectFieldSpec, ProjectFieldSpec, ProjectFieldSpec, ProjectFieldSpec]:
    return (
        ProjectFieldSpec(
            section_title="1. STORY BIBLE",
            subtitle="세계관과 연재 목표",
            guide_text="700~1500자",
            input_label="세계관, 배경, 핵심 인물 전제, 연재 목표를 정리하세요",
            config_key="worldview",
            textarea_key="ta_worldview",
            height=250,
            actions=(
                TextAssistAction(
                    label="STORY_BIBLE 구체화",
                    button_key="assist_worldview_expand",
                    empty_warning="먼저 STORY BIBLE 초안을 적어 주세요.",
                    spinner_text="AI가 STORY BIBLE을 더 구체적으로 다듬는 중입니다...",
                    error_prefix="STORY BIBLE 구체화 중 오류가 발생했습니다",
                    notice="STORY BIBLE 구체화 내용을 반영했습니다.",
                    transform=generator.elaborate_worldview,
                ),
                TextAssistAction(
                    label="STORY_BIBLE 압축",
                    button_key="assist_worldview_compress",
                    empty_warning="압축할 STORY BIBLE 내용이 없습니다.",
                    spinner_text="AI가 STORY BIBLE을 핵심만 남기도록 압축하는 중입니다...",
                    error_prefix="STORY BIBLE 압축 중 오류가 발생했습니다",
                    notice="STORY BIBLE 압축 내용을 반영했습니다.",
                    transform=generator.compress_worldview,
                ),
            ),
        ),
        ProjectFieldSpec(
            section_title="2. STYLE GUIDE",
            subtitle="문체와 서술 규칙",
            guide_text="200~600자",
            input_label="시점, 문장 길이, 대사 비중, 금지 표현 등을 정리하세요",
            config_key="tone_and_manner",
            textarea_key="ta_tone",
            height=250,
            actions=(
                TextAssistAction(
                    label="STYLE_GUIDE 정리",
                    button_key="assist_tone_structure",
                    empty_warning="먼저 STYLE GUIDE 초안을 적어 주세요.",
                    spinner_text="AI가 STYLE GUIDE를 규칙 목록으로 정리하는 중입니다...",
                    error_prefix="STYLE GUIDE 정리 중 오류가 발생했습니다",
                    notice="STYLE GUIDE 정리 내용을 반영했습니다.",
                    transform=generator.structure_style_guide,
                ),
            ),
        ),
        ProjectFieldSpec(
            section_title="3. CONTINUITY",
            subtitle="고정 설정과 관계도",
            guide_text="300~900자",
            input_label="절대 바뀌면 안 되는 룰, 지명, 관계도, 고정 설정을 적어 주세요",
            config_key="continuity",
            textarea_key="ta_continuity",
            height=250,
            actions=(
                TextAssistAction(
                    label="CONTINUITY 정리",
                    button_key="assist_continuity_structure",
                    empty_warning="먼저 CONTINUITY 초안을 적어 주세요.",
                    spinner_text="AI가 CONTINUITY를 고정 설정 문서로 정리하는 중입니다...",
                    error_prefix="CONTINUITY 정리 중 오류가 발생했습니다",
                    notice="CONTINUITY 정리 내용을 반영했습니다.",
                    transform=generator.structure_continuity,
                ),
            ),
        ),
        ProjectFieldSpec(
            section_title="4. STATE",
            subtitle="현재 상황과 감정선",
            guide_text="150~500자",
            input_label="직전 사건, 미해결 갈등, 현재 감정선과 다음 목표를 적어 주세요",
            config_key="state",
            textarea_key="ta_state",
            height=250,
            actions=(
                TextAssistAction(
                    label="STATE 요약",
                    button_key="assist_state_summarize",
                    empty_warning="먼저 STATE 초안을 적어 주세요.",
                    spinner_text="AI가 STATE를 현재 상황 중심으로 정리하는 중입니다...",
                    error_prefix="STATE 요약 중 오류가 발생했습니다",
                    notice="STATE 요약 내용을 반영했습니다.",
                    transform=generator.summarize_state,
                ),
            ),
        ),
    )


def summarize_text_preview(text: str, *, max_chars: int = 90, empty_fallback: str = "아직 작성되지 않았습니다.") -> str:
    normalized = " ".join(line.strip() for line in str(text).splitlines() if line.strip())
    normalized = re.sub(r"[#*_`]+", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return empty_fallback
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[:max_chars].rstrip()}..."


def build_canon_store_summary(canon_state: dict[str, Any]) -> CanonStoreSummary:
    people = canon_state.get("people", {})
    resources = canon_state.get("resources", {})
    hooks = canon_state.get("hooks", [])
    timeline = canon_state.get("timeline", [])
    return CanonStoreSummary(
        people_count=len(people) if isinstance(people, dict) else 0,
        resources_count=len(resources) if isinstance(resources, dict) else 0,
        hooks_count=len(hooks) if isinstance(hooks, list) else 0,
        timeline_count=len(timeline) if isinstance(timeline, list) else 0,
    )


def build_release_policy_summary(policy: dict[str, Any]) -> ReleasePolicySummary:
    global_policy = policy.get("global", {})
    platforms = policy.get("platforms", {})
    enabled_platforms = tuple(
        sorted(
            platform_name
            for platform_name, platform_config in platforms.items()
            if isinstance(platform_config, dict) and platform_config.get("enabled")
        )
    )
    return ReleasePolicySummary(
        max_daily_releases=int(global_policy.get("max_daily_releases", 0) or 0),
        burst_allowed=bool(global_policy.get("burst_allowed", False)),
        cooldown_failures=int(global_policy.get("cooldown_failures", 0) or 0),
        enabled_platforms=enabled_platforms,
    )


def _normalize_project_section_title(section_title: str) -> str:
    normalized = re.sub(r"^\d+\.\s*", "", str(section_title or "")).strip()
    return normalized or "문서"


def build_project_settings_status_snapshot(
    panels: tuple[Any, ...],
    *,
    canon_summary: CanonStoreSummary,
    release_summary: ReleasePolicySummary,
) -> ProjectSettingsStatusSnapshot:
    filled_count = sum(1 for panel in panels if int(getattr(panel, "char_count", 0) or 0) > 0)
    attention_count = sum(1 for panel in panels if getattr(panel, "status", "") != "적정")
    total_config_chars = sum(int(getattr(panel, "char_count", 0) or 0) for panel in panels)

    warnings: list[str] = []
    recommended_actions: list[str] = []
    for panel in panels:
        section_title = _normalize_project_section_title(getattr(getattr(panel, "spec", None), "section_title", ""))
        char_count = int(getattr(panel, "char_count", 0) or 0)
        status = str(getattr(panel, "status", "") or "")
        if char_count <= 0:
            warnings.append(f"{section_title}이 비어 있습니다.")
            recommended_actions.append(f"{section_title} 초안을 먼저 작성하세요.")
            continue
        if status != "적정":
            warnings.append(f"{section_title} 길이를 조정해야 합니다.")
            recommended_actions.append(f"{section_title}를 AI 보조 버튼으로 압축하거나 정리하세요.")

    structured_store_label = (
        f"Canon {canon_summary.people_count} / 플랫폼 {len(release_summary.enabled_platforms)}"
    )

    return ProjectSettingsStatusSnapshot(
        filled_count=filled_count,
        attention_count=attention_count,
        total_config_chars=total_config_chars,
        previous_summary_status="saved",
        previous_summary_label="사용 안함",
        structured_store_label=structured_store_label,
        warnings=tuple(warnings),
        recommended_actions=tuple(recommended_actions),
    )


def persist_workspace_field(
    context: Any,
    *,
    current_settings: dict[str, str],
    config_key: str,
    value: str,
) -> dict[str, str]:
    updated_settings = dict(current_settings)
    updated_settings[config_key] = value

    if config_key in STORY_BIBLE_FIELD_KEYS:
        context.save_story_bible_sections(
            worldview=updated_settings["worldview"],
            tone_and_manner=updated_settings["tone_and_manner"],
            continuity=updated_settings["continuity"],
        )
        return updated_settings

    if config_key == "state":
        context.save_state(updated_settings["state"])
        return updated_settings

    if config_key == "summary_of_previous":
        context.save_previous_summary(updated_settings["summary_of_previous"])
        return updated_settings

    raise ValueError(f"Unsupported workspace field: {config_key}")


def persist_workspace_settings(context: Any, field_values: dict[str, str]) -> dict[str, str]:
    updated_settings = dict(field_values)
    context.save_story_bible_sections(
        worldview=updated_settings["worldview"],
        tone_and_manner=updated_settings["tone_and_manner"],
        continuity=updated_settings["continuity"],
    )
    context.save_state(updated_settings["state"])
    return updated_settings


def resolve_summary_suggestion_source(pasted_text: str, latest_chapter_path: Path | None) -> tuple[str, str]:
    normalized_pasted_text = str(pasted_text or "").strip()
    if normalized_pasted_text:
        return normalized_pasted_text, "붙여넣은 텍스트"

    if latest_chapter_path and latest_chapter_path.exists():
        return latest_chapter_path.read_text(encoding="utf-8"), f"최근 저장 원고: {latest_chapter_path.name}"

    return "", ""


def apply_pending_project_textarea_updates(session_state: dict[str, Any]) -> None:
    pending_updates = session_state.pop("_pending_project_textarea_updates", None)
    if not pending_updates:
        return

    for textarea_key, textarea_value in pending_updates.items():
        session_state[textarea_key] = textarea_value


def build_project_field_panels(
    specs: tuple[ProjectFieldSpec, ...],
    field_stats: list[dict],
    config: dict,
) -> tuple[ProjectFieldPanel, ...]:
    stats_by_key = {row["key"]: row for row in field_stats}
    pending_panels: list[dict[str, Any]] = []
    first_attention_index: int | None = None

    for index, spec in enumerate(specs):
        row = stats_by_key[spec.config_key]
        preview_text = summarize_text_preview(config.get(spec.config_key, ""))

        needs_attention = row["status"] != "적정"
        if needs_attention and first_attention_index is None:
            first_attention_index = index

        pending_panels.append(
            {
                "spec": spec,
                "char_count": row["chars"],
                "recommended_max_chars": row["recommended_max_chars"],
                "status": row["status"],
                "tip": row["tip"],
                "expander_label": f"{spec.section_title} · {row['chars']:,}자 · {row['status']}",
                "preview_text": preview_text,
            }
        )

    return tuple(
        ProjectFieldPanel(
            spec=item["spec"],
            char_count=item["char_count"],
            recommended_max_chars=item["recommended_max_chars"],
            status=item["status"],
            tip=item["tip"],
            expander_label=item["expander_label"],
            preview_text=item["preview_text"],
            expanded=first_attention_index == index if first_attention_index is not None else False,
        )
        for index, item in enumerate(pending_panels)
    )


def maybe_apply_text_assist(
    generator: Generator,
    config: dict,
    *,
    source_text: str,
    config_key: str,
    textarea_key: str,
    action: TextAssistAction,
    ensure_api_key: Callable[[], bool],
    run_with_status: Callable[..., Any],
) -> None:
    if not st.button(action.label, key=action.button_key, width="stretch"):
        return
    if not source_text.strip():
        st.warning(action.empty_warning)
        return
    if not ensure_api_key():
        return

    transformed_text = run_with_status(
        lambda: action.transform(source_text),
        action.spinner_text,
        error_prefix=action.error_prefix,
    )
    if transformed_text is None:
        return

    persist_workspace_field(
        generator.ctx,
        current_settings=config,
        config_key=config_key,
        value=transformed_text,
    )
    st.session_state["_pending_project_textarea_reset"] = textarea_key
    st.session_state["_pending_project_notice"] = action.notice
    st.rerun()


def render_project_text_field(
    generator: Generator,
    config: dict,
    panel: ProjectFieldPanel,
    *,
    ensure_api_key: Callable[[], bool],
    run_with_status: Callable[..., Any],
) -> str:
    spec = panel.spec
    with st.expander(panel.expander_label, expanded=panel.expanded):
        st.caption(f"{spec.subtitle} · 권장 {panel.recommended_max_chars:,}자")
        st.caption(f"현재 요약: {panel.preview_text}")
        if panel.status != "적정":
            st.info(panel.tip)

        field_text = st.text_area(
            spec.input_label,
            value=config.get(spec.config_key, ""),
            height=spec.height,
            key=spec.textarea_key,
        )

        if spec.actions:
            button_cols = st.columns(len(spec.actions))
            for col, action in zip(button_cols, spec.actions):
                with col:
                    maybe_apply_text_assist(
                        generator,
                        config,
                        source_text=field_text,
                        config_key=spec.config_key,
                        textarea_key=spec.textarea_key,
                        action=action,
                        ensure_api_key=ensure_api_key,
                        run_with_status=run_with_status,
                    )

        if spec.config_key == "state":
            source_key = "workspace_state_source_text"
            if source_key not in st.session_state:
                st.session_state[source_key] = ""

            latest_chapter_path = find_latest_sample_chapter(generator.chapters_dir)
            st.caption("직접 붙여넣은 텍스트나 최근 저장 원고를 기준으로 STATE 제안안을 채울 수 있습니다.")
            if latest_chapter_path:
                st.caption(f"소스를 비워 두면 최근 저장 원고 `{latest_chapter_path.name}` 를 사용합니다.")
            st.text_area(
                "STATE 제안 소스 텍스트",
                key=source_key,
                height=120,
                help="직접 붙여넣은 텍스트를 우선 사용하고, 비어 있으면 최근 저장 원고를 대신 사용합니다.",
            )
            if st.button("AI 제안으로 STATE 채우기", key="fill_state_from_source", width="stretch"):
                if ensure_api_key():
                    source_text, source_label = resolve_summary_suggestion_source(
                        st.session_state.get(source_key, ""),
                        latest_chapter_path,
                    )
                    if not source_text:
                        st.warning("붙여넣은 텍스트가 없고, 사용할 최근 저장 원고도 찾지 못했습니다.")
                    else:
                        suggested_state = run_with_status(
                            lambda: generator.summarize_state(source_text),
                            spinner_text="AI가 STATE 제안안을 생성하는 중입니다...",
                            error_prefix="STATE 제안 생성 중 오류가 발생했습니다",
                        )
                        if suggested_state is not None:
                            pending_updates = st.session_state.setdefault("_pending_project_textarea_updates", {})
                            pending_updates[spec.textarea_key] = suggested_state
                            st.session_state["_pending_project_notice"] = f"{source_label} 기준 STATE 제안안을 입력창에 채웠습니다."
                            st.rerun()

        return field_text


def render_character_management_panel(generator: Generator, config: dict) -> None:
    with st.expander("등장인물 JSON 관리", expanded=False):
        st.markdown("### 1. AI로 주요 등장인물 추출")
        st.info("STORY BIBLE, CONTINUITY, STATE, 이전 줄거리 요약을 바탕으로 주요 캐릭터를 자동 추출합니다.")

        if st.button("설정 문서 기반으로 등장인물 자동 추출", type="primary", width="stretch"):
            has_source = any(
                config.get(field, "").strip()
                for field in ("worldview", "continuity", "state", "summary_of_previous")
            )
            if not has_source:
                st.warning("먼저 STORY BIBLE, CONTINUITY, STATE 중 하나 이상을 채워 주세요.")
            else:
                with st.spinner("AI가 등장인물을 추출하는 중입니다..."):
                    try:
                        extracted_json_str = generator.generate_characters(
                            worldview=config.get("worldview", ""),
                            continuity=config.get("continuity", ""),
                            state=config.get("state", ""),
                            summary_of_previous=config.get("summary_of_previous", ""),
                        )
                        parsed_chars = json.loads(extracted_json_str)
                        generator.ctx.save_characters(parsed_chars)
                        st.success("등장인물을 저장했습니다.")
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error("AI 응답에서 올바른 JSON 배열을 추출하지 못했습니다.")
                        st.code(extracted_json_str)
                    except ValueError as exc:
                        st.error(f"등장인물 형식이 올바르지 않습니다: {exc}")
                    except LLMError as exc:
                        st.error(f"등장인물 추출 중 오류가 발생했습니다: {exc}")
                    except Exception as exc:
                        st.error(f"등장인물 추출 중 예기치 못한 오류가 발생했습니다: {exc}")

        st.divider()
        st.markdown("### 2. 수동 편집")
        st.info("필요하면 JSON을 직접 수정해서 저장할 수 있습니다.")

        characters = generator.ctx.get_characters()
        char_json_str = json.dumps(characters, ensure_ascii=False, indent=4) if characters else "[]"
        chars_text = st.text_area("현재 등장인물 JSON", value=char_json_str, height=320)

        if st.button("등장인물 저장", key="save_char"):
            try:
                parsed_chars = json.loads(chars_text)
                generator.ctx.save_characters(parsed_chars)
                st.success("등장인물 정보를 저장했습니다.")
            except json.JSONDecodeError:
                st.error("JSON 문법을 확인해 주세요.")
            except ValueError as exc:
                st.error(f"등장인물 형식 오류입니다: {exc}")
            except Exception as exc:
                st.error(f"알 수 없는 오류가 발생했습니다: {exc}")


def render_structured_store_overview(generator: Generator) -> None:
    canon_summary = build_canon_store_summary(generator.ctx.canon_store.load_current_state())
    release_summary = build_release_policy_summary(generator.ctx.release_policy_store.load())
    enabled_platforms = ", ".join(release_summary.enabled_platforms) if release_summary.enabled_platforms else "없음"

    with st.expander("구조화 저장소 현황", expanded=False):
        st.caption("프로젝트 설정 탭은 Story Bible 편집값을 직접 저장하고, Canon / Release Policy는 읽기 전용 기준선으로 보여 줍니다.")

        canon_col, release_col = st.columns(2)
        with canon_col:
            st.markdown("### CANON")
            st.write(f"- 인물: {canon_summary.people_count}")
            st.write(f"- 자원: {canon_summary.resources_count}")
            st.write(f"- 훅: {canon_summary.hooks_count}")
            st.write(f"- 타임라인: {canon_summary.timeline_count}")
        with release_col:
            st.markdown("### RELEASE POLICY")
            st.write(f"- 일일 최대 발행: {release_summary.max_daily_releases}")
            st.write(f"- 버스트 허용: {'예' if release_summary.burst_allowed else '아니오'}")
            st.write(f"- 실패 쿨다운 기준: {release_summary.cooldown_failures}")
            st.write(f"- 활성 플랫폼: {enabled_platforms}")

        st.caption("저장소 경로")
        st.code(generator.ctx.story_bible_store.story_bible_path.as_posix(), language="text")
        st.code(generator.ctx.canon_store.current_state_path.as_posix(), language="text")
        st.code(generator.ctx.release_policy_store.policy_path.as_posix(), language="text")


def render_sidebar(
    *,
    normalize_project_name: Callable[[str], tuple[str | None, str | None]],
    get_project_list: Callable[[], list[str]],
    clear_project_state: Callable[[], None],
    get_cached_generator: Callable[[str], Generator],
    load_project_textareas: Callable[[dict], None],
    clear_cached_resources: Callable[[], None],
    set_env_variable: Callable[[str, str], None],
) -> str:
    with st.sidebar:
        st.header("작품 관리")

        new_project_name = st.text_input(
            "새 작품 이름",
            placeholder="예: 회귀 아카데미 판타지",
            help="공백을 써도 됩니다. 연속된 공백은 하나로 정리됩니다.",
        )
        if st.button("새 작품 추가", width="stretch"):
            project_name, project_name_error = normalize_project_name(new_project_name)
            if project_name_error:
                st.error(project_name_error)
            else:
                target_dir = DATA_PROJECTS_DIR / project_name
                if target_dir.exists():
                    st.error("이미 존재하는 작품 이름입니다.")
                else:
                    Generator(project_name=project_name)
                    clear_project_state()
                    st.session_state["current_project"] = project_name
                    st.success(f"'{project_name}' 작품을 만들었습니다.")
                    st.rerun()

        st.divider()

        projects = get_project_list()
        if not projects:
            st.warning("저장된 작품이 없습니다. 먼저 작품을 만들어 주세요.")
            st.stop()

        current_project = st.session_state.get("current_project")
        if current_project not in projects:
            st.session_state["current_project"] = projects[0]

        selected_project = st.selectbox(
            "현재 작업 작품",
            options=projects,
            index=projects.index(st.session_state["current_project"]),
        )
        if selected_project != st.session_state["current_project"]:
            clear_project_state()
            st.session_state["current_project"] = selected_project
            temp_generator = get_cached_generator(selected_project)
            load_project_textareas(temp_generator.ctx.get_workspace_settings())
            st.rerun()

        with st.expander("현재 작품 삭제", expanded=False):
            current_project_name = st.session_state["current_project"]
            st.warning(f"정말 '{current_project_name}' 작품을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.")
            delete_confirmation = st.text_input(
                "확인용으로 작품 이름을 다시 입력해 주세요.",
                key="delete_project_confirm",
                placeholder=current_project_name,
            )
            delete_disabled = delete_confirmation.strip() != current_project_name
            if st.button("작품 삭제", type="primary", width="stretch", disabled=delete_disabled):
                target_dir = DATA_PROJECTS_DIR / current_project_name
                try:
                    shutil.rmtree(target_dir)
                    clear_cached_resources()
                    clear_project_state()
                    st.session_state.pop("delete_project_confirm", None)
                    st.session_state.pop("current_project", None)

                    remaining_projects = get_project_list()
                    if remaining_projects:
                        st.session_state["current_project"] = remaining_projects[0]

                    st.success(f"'{current_project_name}' 작품을 삭제했습니다.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"작품 삭제 중 오류가 발생했습니다: {exc}")

        runtime_api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        secure_storage_available = has_secure_storage()
        secure_api_key_exists = bool(get_secure_api_key())
        plain_env_key_exists = env_file_has_key()
        current_backend_mode = resolve_backend_mode(os.getenv("GEMINI_BACKEND", "auto"))
        current_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        detected_cli_status = probe_gemini_cli()
        stored_cli_status = st.session_state.get("gemini_cli_status")
        if isinstance(stored_cli_status, GeminiCliStatus) and stored_cli_status.path == detected_cli_status.path:
            cli_status = replace(stored_cli_status, version=detected_cli_status.version or stored_cli_status.version)
        else:
            cli_status = detected_cli_status
            st.session_state["gemini_cli_status"] = cli_status

        st.divider()
        diagnostics_summary = get_sidebar_summary(st.session_state["current_project"])
        automation_store = AutomationStore(project_name=st.session_state["current_project"])
        automation_config = automation_store.load_config()
        automation_runtime = automation_store.load_runtime()
        st.caption(f"LLM Diagnostics: {format_sidebar_summary(diagnostics_summary)}")
        st.caption(f"자동화: {format_schedule_summary(automation_config)} / {format_runtime_status(automation_runtime)}")
        if secure_api_key_exists:
            st.caption("API 상태: 보안 저장소 사용 중")
        elif runtime_api_key:
            st.caption("API 상태: 이번 실행에만 적용됨")
        else:
            st.caption("API 상태: 설정 안 됨")
        st.caption(f"LLM 백엔드: {BACKEND_MODE_OPTIONS[current_backend_mode]}")
        st.caption(f"Gemini CLI 상태: {format_cli_status(cli_status)}")

        with st.expander("API / 모델 설정", expanded=False):
            if secure_api_key_exists:
                st.caption("보안 저장소에 API 키가 저장되어 있으며 앱 시작 시 자동 로드됩니다.")
            elif runtime_api_key:
                st.caption("현재 실행 환경에 API 키가 적용되어 있습니다.")
            else:
                st.caption("설정된 API 키가 없습니다.")

            if plain_env_key_exists:
                st.warning("`.env`에 평문 API 키가 남아 있습니다. 가능하면 보안 저장소로 옮기는 편이 안전합니다.")

            new_api_key = st.text_input(
                "Google API Key",
                value="",
                type="password",
                help="쉼표로 여러 키를 넣으면 순차적으로 fallback 됩니다.",
            )
            runtime_col, secure_col = st.columns(2)
            with runtime_col:
                if st.button("이번 실행에만 적용", width="stretch"):
                    if new_api_key.strip():
                        set_runtime_api_key(new_api_key.strip())
                        st.success("API 키를 현재 실행에만 적용했습니다. 앱을 재시작하면 사라집니다.")
                        st.rerun()
            with secure_col:
                secure_button_disabled = not secure_storage_available
                if st.button("보안 저장소에 저장", width="stretch", disabled=secure_button_disabled):
                    ok, message = save_api_key_to_secure_storage(new_api_key.strip())
                    if ok:
                        load_dotenv(override=True)
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

            if not secure_storage_available:
                st.info("보안 저장소를 사용하려면 `keyring`이 필요합니다. 현재는 평문 저장 없이 런타임 적용만 가능합니다.")

            if secure_api_key_exists:
                if st.button("보안 저장소의 API 키 삭제", width="stretch"):
                    ok, message = delete_api_key_from_secure_storage()
                    if ok:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

            with st.expander("고급: 평문 `.env` 저장", expanded=False):
                st.warning("이 옵션은 API 키를 프로젝트의 `.env` 파일에 평문으로 저장합니다.")
                if st.button("그래도 `.env`에 저장", width="stretch"):
                    if new_api_key.strip():
                        set_env_variable("GOOGLE_API_KEY", new_api_key.strip())
                        load_dotenv(override=True)
                        st.success("API 키를 `.env`에 저장했습니다.")
                        st.rerun()

            available_models = get_available_models()
            selected_model = st.selectbox(
                "Gemini 모델",
                options=available_models,
                index=available_models.index(current_model) if current_model in available_models else 0,
            )
            if selected_model != current_model:
                set_env_variable("GEMINI_MODEL", selected_model)
                load_dotenv(override=True)
                st.session_state.pop("gemini_cli_status", None)
                st.success(f"기본 모델을 '{selected_model}'로 변경했습니다.")
                st.rerun()

            selected_backend_mode = st.selectbox(
                "LLM 백엔드",
                options=list(BACKEND_MODE_OPTIONS.keys()),
                index=list(BACKEND_MODE_OPTIONS.keys()).index(current_backend_mode),
                format_func=lambda key: BACKEND_MODE_OPTIONS[key],
                help="auto는 Gemini CLI를 먼저 시도하고, 실패하면 API로 넘어갑니다.",
            )
            if selected_backend_mode != current_backend_mode:
                set_env_variable("GEMINI_BACKEND", selected_backend_mode)
                load_dotenv(override=True)
                st.success(f"LLM 백엔드를 '{BACKEND_MODE_OPTIONS[selected_backend_mode]}'로 변경했습니다.")
                st.rerun()

            st.caption("Gemini CLI는 사용자가 별도로 OAuth 로그인해 둔 공식 CLI를 그대로 사용합니다.")
            if cli_status.path:
                st.code(cli_status.path, language="text")
            if cli_status.version:
                st.caption(f"Gemini CLI 버전: {cli_status.version}")
            if cli_status.message:
                st.caption(cli_status.message)

            if st.button("CLI 연결 테스트", width="stretch"):
                with st.spinner("Gemini CLI 연결을 확인하는 중입니다..."):
                    tested_status = test_gemini_cli_connection(selected_model, executable_path=cli_status.path)
                st.session_state["gemini_cli_status"] = tested_status
                if tested_status.authenticated is True:
                    st.success("Gemini CLI OAuth 연결이 정상입니다.")
                elif tested_status.authenticated is False:
                    st.warning(tested_status.message)
                elif not tested_status.available:
                    st.error(tested_status.message)
                else:
                    st.info(tested_status.message)
                st.rerun()

            st.link_button(
                "토큰 사용량 보기",
                "https://aistudio.google.com/app/usage?timeRange=last-28-days",
                width="stretch",
            )

    return st.session_state["current_project"]


def render_project_settings_tab(
    app: Any,
    *,
    ensure_api_key: Callable[[], bool],
    run_with_status: Callable[..., Any],
) -> None:
    generator = app.generator

    pending_widget_reset = st.session_state.pop("_pending_project_textarea_reset", None)
    if pending_widget_reset:
        reset_keys = pending_widget_reset if isinstance(pending_widget_reset, list) else [pending_widget_reset]
        for widget_key in reset_keys:
            st.session_state.pop(widget_key, None)
    apply_pending_project_textarea_updates(st.session_state)

    st.header("프로젝트 통합 설정")
    st.markdown(
        "네 가지 문서(`STORY_BIBLE`, `STYLE_GUIDE`, `CONTINUITY`, `STATE`)가 "
        "AI의 기본 입력으로 들어가며 작품의 고정 설정과 현재 상태를 결정합니다."
    )
    st.caption("AI 보조 버튼은 각 필드별로만 동작하므로 필요한 부분만 정리할 수 있습니다.")

    pending_project_notice = st.session_state.pop("_pending_project_notice", "")
    if pending_project_notice:
        st.success(pending_project_notice)

    config = generator.ctx.get_workspace_settings()
    field_stats = get_field_stats(config)
    budget_recommendations = get_budget_recommendations(config)

    specs = build_project_field_specs(generator)
    panels = build_project_field_panels(specs, field_stats, config)
    canon_summary = build_canon_store_summary(generator.ctx.canon_store.load_current_state())
    release_summary = build_release_policy_summary(generator.ctx.release_policy_store.load())
    status_snapshot = build_project_settings_status_snapshot(
        panels,
        canon_summary=canon_summary,
        release_summary=release_summary,
    )

    overview_col, attention_col, structured_col = st.columns(3)
    with overview_col:
        st.metric("핵심 문서 준비도", f"{status_snapshot.filled_count}/4")
    with attention_col:
        st.metric("확인 필요", f"{status_snapshot.attention_count}개")
    with structured_col:
        st.metric("구조화 저장소", status_snapshot.structured_store_label)

    st.caption(f"핵심 설정 총 글자 수: {status_snapshot.total_config_chars:,}자")
    if status_snapshot.attention_count:
        st.caption("비어 있거나 길이 조정이 필요한 문서는 아래 고급 편집에서 우선 확인하세요.")
    else:
        st.caption("핵심 네 문서가 모두 채워져 있습니다. 필요할 때만 고급 편집을 열어 수정하면 됩니다.")

    st.divider()
    st.subheader("주요 경고 / 다음 작업")
    warning_col, action_col = st.columns(2)
    with warning_col:
        st.markdown("### 주요 경고")
        if status_snapshot.warnings:
            for warning_text in status_snapshot.warnings:
                st.write(f"- {warning_text}")
        else:
            st.info("현재 눈에 띄는 설정 경고는 없습니다.")
    with action_col:
        st.markdown("### 다음 권장 작업")
        if status_snapshot.recommended_actions:
            for action_text in status_snapshot.recommended_actions:
                st.write(f"- {action_text}")
        else:
            st.info("핵심 문서 기준선이 안정적입니다. 필요한 경우만 세부 편집으로 내려가세요.")

    st.divider()
    with st.expander("1. 고급 편집", expanded=status_snapshot.attention_count > 0 or status_snapshot.filled_count < 4):
        with st.expander("길이 가이드와 압축 팁", expanded=False):
            total_config_chars = sum(row["chars"] for row in field_stats)
            st.metric("설정 문서 총 글자 수", f"{total_config_chars:,}자")
            st.dataframe(
                [
                    {
                        "문서": row["label"],
                        "현재 글자 수": row["chars"],
                        "권장 최대": row["recommended_max_chars"],
                        "상태": row["status"],
                    }
                    for row in field_stats
                ],
                width="stretch",
                hide_index=True,
            )
            for recommendation in budget_recommendations:
                st.write(f"- {recommendation}")

        field_values: dict[str, str] = {}
        for panel in panels:
            field_values[panel.spec.config_key] = render_project_text_field(
                generator,
                config,
                panel,
                ensure_api_key=ensure_api_key,
                run_with_status=run_with_status,
            )

        st.divider()
        save_col, info_col = st.columns([1, 4])
        with save_col:
            if st.button("4개 문서 저장", type="primary", width="stretch"):
                persist_workspace_settings(generator.ctx, field_values)
                st.success("프로젝트 설정을 저장했습니다.")
        with info_col:
            st.info("필요한 문서만 저장해도 되지만, 네 문서를 같이 정리하면 생성 품질이 더 안정적입니다.")

    st.divider()
    with st.expander("2. 보조 관리", expanded=False):
        st.caption("핵심 문서 밖의 보조 기준선, 구조화 저장소, 등장인물, 진단은 필요할 때만 여세요.")
        st.caption("자주 쓰는 편집보다 기준선 점검과 보조 자료 관리에 가까운 영역입니다.")

        st.divider()
        render_structured_store_overview(generator)
        st.divider()
        render_character_management_panel(generator, config)
        st.divider()
        render_diagnostics_panel(generator.ctx.project_name, key_prefix="workspace_diag")
