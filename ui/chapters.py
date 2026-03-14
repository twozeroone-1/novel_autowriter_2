import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, TypeVar

import streamlit as st

from core.generator import Generator
from core.llm import LLMError
from core.llm_backend import GeminiCliStatus, get_backend_gate_error, probe_gemini_cli, resolve_backend_mode
from core.token_budget import (
    estimate_generation_cost_report,
    get_budget_recommendations,
    get_field_stats,
)


@dataclass(frozen=True)
class WorkflowStep:
    label: str
    state: str


def build_workflow_steps(labels: tuple[str, ...], current_step: int) -> tuple[WorkflowStep, ...]:
    steps: list[WorkflowStep] = []
    for index, label in enumerate(labels):
        if index < current_step:
            state = "완료"
        elif index == current_step:
            state = "현재 단계"
        else:
            state = "다음 단계"
        steps.append(WorkflowStep(label=label, state=state))
    return tuple(steps)


def build_session_bound_text_area_kwargs(
    widget_key: str,
    initial_value: str,
    session_state: Mapping[str, Any],
) -> dict[str, str]:
    kwargs: dict[str, str] = {"key": widget_key}
    if widget_key not in session_state:
        kwargs["value"] = initial_value
    return kwargs


def select_context_update_value(suggested_value: str, current_value: str) -> str:
    suggested_text = str(suggested_value).strip()
    if suggested_text:
        return suggested_text
    return str(current_value)


def build_chapter_context_defaults(
    *,
    suggested_state: str,
    suggested_summary: str,
    current_snapshot: Mapping[str, Any],
) -> dict[str, str]:
    return {
        "state": select_context_update_value(suggested_state, str(current_snapshot.get("state", ""))),
        "summary_of_previous": select_context_update_value(
            suggested_summary,
            str(current_snapshot.get("summary_of_previous", "")),
        ),
    }


def persist_chapter_context_update(
    context: Any,
    *,
    state: str,
    summary_of_previous: str,
) -> dict[str, str]:
    normalized_state = str(state)
    normalized_summary = str(summary_of_previous)
    context.save_state(normalized_state)
    context.save_previous_summary(normalized_summary)
    return {
        "state": normalized_state,
        "summary_of_previous": normalized_summary,
    }


def render_workflow_steps(labels: tuple[str, ...], current_step: int) -> None:
    steps = build_workflow_steps(labels, current_step)
    cols = st.columns(len(steps))
    for index, (col, step) in enumerate(zip(cols, steps), start=1):
        with col:
            st.caption(step.state)
            st.markdown(f"**{index}. {step.label}**")


def ensure_api_key() -> bool:
    backend_mode = resolve_backend_mode(os.getenv("GEMINI_BACKEND", "auto"))
    has_api_key = bool(os.getenv("GOOGLE_API_KEY", "").strip())
    cli_status: GeminiCliStatus | None = None
    if backend_mode in {"auto", "cli"}:
        stored_status = st.session_state.get("gemini_cli_status")
        if isinstance(stored_status, GeminiCliStatus):
            cli_status = stored_status
        else:
            cli_status = probe_gemini_cli()
            st.session_state["gemini_cli_status"] = cli_status

    gate_error = get_backend_gate_error(
        backend_mode,
        has_api_key=has_api_key,
        cli_status=cli_status,
    )
    if gate_error is None:
        return True
    st.error(gate_error)
    return False


def format_usd(value: float | None) -> str:
    if value is None:
        return "-"
    if value < 0.0001:
        return f"${value:.6f}"
    return f"${value:.4f}"


def open_folder(path: Path) -> None:
    resolved_path = Path(path).resolve()
    try:
        if hasattr(os, "startfile"):
            os.startfile(str(resolved_path))
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(resolved_path)])
            return
        if sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(resolved_path)])
            return
    except Exception as exc:
        st.error(f"폴더를 여는 중 오류가 발생했습니다: {exc}")
        return

    st.error("현재 환경에서는 폴더 열기를 지원하지 않습니다.")


def sync_summary_after_save(generator: Generator, chapter_content: str, save_label: str) -> None:
    with st.spinner("저장한 내용을 다음 회차용 컨텍스트에 반영하는 중입니다..."):
        try:
            generator.summarize_and_update_context(chapter_content)
        except LLMError as exc:
            st.warning(f"{save_label} 이후 이전 줄거리 요약 갱신에 실패했습니다: {exc}")
        except Exception as exc:
            st.warning(f"{save_label} 이후 이전 줄거리 요약 갱신 중 예상치 못한 오류가 발생했습니다: {exc}")
        else:
            st.success("이전 줄거리 요약을 갱신했습니다.")


T = TypeVar("T")


def run_with_status(
    action: Callable[[], T],
    spinner_text: str,
    *,
    error_prefix: str,
    llm_error_prefix: str | None = None,
    success_message: str | None = None,
) -> T | None:
    with st.spinner(spinner_text):
        try:
            result = action()
        except LLMError as exc:
            st.error(f"{llm_error_prefix or error_prefix}: {exc}")
            return None
        except Exception as exc:
            st.error(f"{error_prefix}: {exc}")
            return None

    if success_message:
        st.success(success_message)
    return result


def save_markdown_document_and_notify(
    generator: Generator,
    *,
    filename_title: str,
    content: str,
    error_prefix: str,
    success_prefix: str,
    heading_title: str | None = None,
) -> str | None:
    try:
        saved_path = generator.save_markdown_document(
            filename_title=filename_title,
            content=content,
            heading_title=heading_title,
        )
    except Exception as exc:
        st.error(f"{error_prefix}: {exc}")
        return None

    st.success(f"{success_prefix}: `{saved_path}`")
    return saved_path


def save_chapter_and_notify(
    generator: Generator,
    *,
    title: str,
    content: str,
    error_prefix: str,
    success_prefix: str,
    summary_failure_prefix: str | None = None,
) -> str | None:
    try:
        saved_path = generator.save_chapter(title, content)
    except Exception as exc:
        st.error(f"{error_prefix}: {exc}")
        return None

    st.success(f"{success_prefix}: `{saved_path}`")
    if summary_failure_prefix:
        st.info("저장된 원고의 컨텍스트 반영은 AI 제안 검토 후 진행하도록 바뀌었습니다.")
    return saved_path


def render_generation_budget_panel(
    generator: Generator,
    *,
    user_instruction: str,
    target_length: int,
    use_plot: bool,
    plot_strength: str,
) -> None:
    budget_config = generator.ctx.get_config()
    field_stats = get_field_stats(budget_config)
    recommendations = get_budget_recommendations(budget_config)
    total_core_chars = sum(row["chars"] for row in field_stats)
    current_model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    with st.expander("토큰/비용 예상", expanded=False):
        st.caption("기본 길이 가이드는 즉시 계산하고, 정확한 토큰 수는 `countTokens` API 호출로 계산합니다.")
        st.metric("설정 문서 총 글자수", f"{total_core_chars:,}자")
        st.dataframe(
            [
                {
                    "문서": row["label"],
                    "현재 글자수": row["chars"],
                    "권장 최대": row["recommended_max_chars"],
                    "상태": row["status"],
                }
                for row in field_stats
            ],
            use_container_width=True,
            hide_index=True,
        )
        for recommendation in recommendations:
            st.write(f"- {recommendation}")
        st.caption("보통은 `PREVIOUS_SUMMARY`와 `STYLE_GUIDE`/`CONTINUITY`를 먼저 줄이는 편이 가장 효과적입니다.")

        calc_disabled = not bool(os.getenv("GOOGLE_API_KEY"))
        if calc_disabled:
            st.caption("정확한 계산을 하려면 GOOGLE_API_KEY가 필요합니다.")

        if st.button("정확히 계산하기 (countTokens API)", key="btn_estimate_tokens", disabled=calc_disabled):
            report = run_with_status(
                lambda: estimate_generation_cost_report(
                    generator=generator,
                    instruction=user_instruction,
                    target_length=target_length,
                    include_plot=use_plot,
                    plot_strength=plot_strength,
                    model_name=current_model_name,
                ),
                "현재 설정과 입력 기준으로 토큰과 비용을 계산하는 중입니다...",
                error_prefix="토큰 계산 중 오류가 발생했습니다",
            )
            if report is None:
                st.session_state.pop("token_budget_report", None)
            else:
                st.session_state["token_budget_report"] = report
                st.session_state["token_budget_error"] = ""

        token_budget_error = st.session_state.get("token_budget_error", "")
        if token_budget_error:
            st.error(f"토큰 계산 중 오류가 발생했습니다: {token_budget_error}")

        report = st.session_state.get("token_budget_report")
        if not report:
            return

        current_prompt_chars = len(
            generator.ctx.build_generation_prompt(
                user_instruction,
                target_length,
                include_plot=use_plot,
                plot_strength=plot_strength,
            )
        )
        report_is_stale = (
            report.get("prompt_chars") != current_prompt_chars
            or report.get("target_length") != target_length
            or report.get("include_plot") != use_plot
            or report.get("plot_strength") != plot_strength
        )
        if report_is_stale:
            st.info("입력값이 바뀌어 현재 계산값이 이전 조건 기준일 수 있습니다. 다시 계산해 주세요.")

        metric_col1, metric_col2, metric_col3 = st.columns(3)
        with metric_col1:
            st.metric("입력 토큰", f"{report['input_tokens']:,}")
        with metric_col2:
            st.metric("예상 출력 토큰", f"{report['estimated_output_tokens']:,}")
        with metric_col3:
            st.metric("모델", report["model_name"])

        st.caption(
            f"프롬프트 {report['prompt_tokens']:,} + 시스템 {report['system_tokens']:,} 토큰. "
            f"출력 추정 기준: {report['output_ratio_source']}"
        )

        cost_col1, cost_col2, cost_col3 = st.columns(3)
        with cost_col1:
            st.metric("예상 입력 비용", format_usd(report["input_cost_usd"]))
        with cost_col2:
            st.metric("예상 출력 비용", format_usd(report["output_cost_usd"]))
        with cost_col3:
            st.metric("예상 총비용", format_usd(report["total_cost_usd"]))

        if report.get("pricing"):
            st.caption("표시된 비용은 Google API 공식 가격 기준 추정치입니다.")
        else:
            st.caption("현재 모델의 가격 정보가 없어 비용은 계산하지 못했습니다.")


def render_generation_tab(app: Any) -> None:
    generator = app.generator

    st.header("다음 회차 생성")
    st.caption("프로젝트 설정과 등장인물 정보가 자동으로 반영됩니다.")
    with st.expander("반영되는 파일 보기", expanded=False):
        st.code(app.config_path_hint, language="text")
        st.code(app.chars_path_hint, language="text")

    chapter_title = st.text_input("회차 제목 (저장 파일명)", value="2화 첫 만남")
    user_instruction = st.text_area(
        "이번 회차 전개 지시사항",
        value="주인공이 낯선 도시에서 길을 잃고 중요한 조력자를 처음 만나는 장면을 긴장감 있게 구성해 주세요.",
        height=150,
    )
    target_length = st.number_input(
        "생성 분량(글자수 목표)",
        min_value=500,
        max_value=20000,
        value=5000,
        step=500,
        help="AI가 목표 분량에 맞춰 서술 밀도를 조절합니다.",
    )

    saved_plot_outline = generator.ctx.get_plot_outline()
    use_plot = st.checkbox(
        "저장한 대형 플롯을 이번 회차 생성에 반영",
        value=False,
        key="gen_use_plot",
        disabled=not bool(saved_plot_outline),
    )
    plot_strength = st.selectbox(
        "플롯 반영 강도",
        options=["loose", "balanced", "strict"],
        index=1,
        key="gen_plot_strength",
        disabled=not use_plot,
        help="loose: 느슨한 참고 / balanced: 권장 / strict: 플롯 우선",
    )
    if not saved_plot_outline:
        st.caption("저장한 플롯이 없어 플롯 반영 옵션은 비활성화되어 있습니다. [1] 프로젝트 통합 설정 > 대형 플롯에서 먼저 생성해 주세요.")

    render_generation_budget_panel(
        generator,
        user_instruction=user_instruction,
        target_length=target_length,
        use_plot=use_plot,
        plot_strength=plot_strength,
    )

    action_col, folder_col = st.columns([1, 2])
    with action_col:
        generate_btn = st.button("초안 생성", type="primary")
    with folder_col:
        if st.button("저장 폴더 열기", key="open_folder_1"):
            open_folder(generator.chapters_dir)

    if generate_btn:
        if not ensure_api_key():
            pass
        elif not user_instruction.strip():
            st.warning("지시사항을 입력해 주세요.")
        else:
            draft = run_with_status(
                lambda: generator.create_chapter(
                    user_instruction,
                    target_length,
                    include_plot=use_plot,
                    plot_strength=plot_strength,
                ),
                f"초안을 생성하는 중입니다 (목표 {target_length:,}자)...",
                llm_error_prefix="초안 생성 중 오류가 발생했습니다",
                error_prefix="초안 생성 중 예상치 못한 오류가 발생했습니다",
                success_message="초안 생성이 완료되었습니다.",
            )
            if draft is not None:
                st.session_state["current_draft"] = draft
                st.session_state["current_title"] = chapter_title.strip() or "무제"
                st.session_state["edited_draft"] = draft
                st.session_state.pop("review_report", None)
                st.session_state.pop("reviewing_draft", None)
                st.session_state.pop("reviewing_title", None)
                st.session_state.pop("revised_draft", None)
                st.session_state.pop("edited_revised_draft", None)

    if "current_draft" not in st.session_state:
        return

    st.divider()
    st.subheader("생성된 초안")
    st.text_area(
        "수정 가능한 초안",
        height=400,
        **build_session_bound_text_area_kwargs(
            "edited_draft",
            st.session_state["current_draft"],
            st.session_state,
        ),
    )

    save_col, folder_col = st.columns([1, 2])
    with save_col:
        save_draft_btn = st.button("현재 초안 저장(.md)")
    with folder_col:
        if st.button("저장 폴더 열기", key="open_folder_2"):
            open_folder(generator.chapters_dir)

    if save_draft_btn:
        save_chapter_and_notify(
            generator,
            title=st.session_state["current_title"],
            content=st.session_state["edited_draft"],
            error_prefix="초안 저장 중 오류가 발생했습니다",
            success_prefix="초안을 저장했습니다",
            summary_failure_prefix="초안 저장",
        )

    st.divider()
    st.subheader("컨텍스트 제안")
    st.caption("초안을 기준으로 다음 회차용 STATE와 누적 PREVIOUS SUMMARY 제안을 만들 수 있습니다.")

    if st.button("초안 기준 컨텍스트 제안 생성", key="generation_generate_context", use_container_width=True):
        context_result = run_with_status(
            lambda: generator.build_context_suggestions(st.session_state["edited_draft"]),
            "STATE/PREVIOUS SUMMARY 제안을 생성하는 중입니다...",
            llm_error_prefix="컨텍스트 제안 생성 중 오류가 발생했습니다",
            error_prefix="컨텍스트 제안 생성 중 예상치 못한 오류가 발생했습니다",
        )
        if context_result is not None:
            st.session_state["generation_context_result"] = context_result
            st.session_state.pop("generation_context_state", None)
            st.session_state.pop("generation_context_summary", None)

    generation_context_result = st.session_state.get("generation_context_result", {})
    if generation_context_result:
        if generation_context_result.get("state_error"):
            st.warning(f"STATE 제안 생성에 실패했습니다: {generation_context_result['state_error']}")
        if generation_context_result.get("summary_error"):
            st.warning(f"PREVIOUS SUMMARY 제안 생성에 실패했습니다: {generation_context_result['summary_error']}")

        current_snapshot = generator.ctx.get_workspace_settings()
        generation_defaults = build_chapter_context_defaults(
            suggested_state=generation_context_result.get("new_state", ""),
            suggested_summary=generation_context_result.get("new_summary", ""),
            current_snapshot=current_snapshot,
        )

        state_col, summary_col = st.columns(2)
        with state_col:
            generation_state = st.text_area(
                "검토 후 반영할 CURRENT STATE",
                value=generation_defaults["state"],
                height=200,
                key="generation_context_state",
            )
        with summary_col:
            generation_summary = st.text_area(
                "검토 후 반영할 PREVIOUS SUMMARY",
                value=generation_defaults["summary_of_previous"],
                height=200,
                key="generation_context_summary",
            )

        if st.button("프로젝트 컨텍스트에 반영", key="apply_generation_context", use_container_width=True):
            persist_chapter_context_update(
                generator.ctx,
                state=generation_state,
                summary_of_previous=generation_summary,
            )
            st.success("STATE와 PREVIOUS SUMMARY를 반영했습니다.")


def render_review_tab(app: Any) -> None:
    generator = app.generator
    reviewer = app.reviewer

    st.header("원고 검수")
    st.markdown("세계관 충돌, 문맥 문제, 문장 완성도 기준으로 원고를 검토하고 수정본까지 만들 수 있습니다.")
    review_step = 0
    if "revised_draft" in st.session_state:
        review_step = 2
    elif "review_report" in st.session_state:
        review_step = 1
    render_workflow_steps(("검수 대상 선택", "검수 리포트 생성", "수정본 저장"), review_step)

    saved_files: list[str] = []
    if generator.chapters_dir.exists():
        saved_files = sorted(
            file.name for file in generator.chapters_dir.iterdir() if file.is_file() and file.suffix == ".md"
        )

    selected_file = st.selectbox("검수할 원고 파일 선택", options=["새로 생성한 초안 사용"] + saved_files)

    draft_to_review = ""
    review_title = "임시_제목"
    if selected_file == "새로 생성한 초안 사용":
        if "current_draft" in st.session_state:
            draft_to_review = st.session_state["current_draft"]
            review_title = st.session_state.get("current_title", "새 초안")
        else:
            st.info("메모리에 초안이 없습니다. 저장된 파일을 고르거나 [2] 탭에서 먼저 생성해 주세요.")
    else:
        file_path = generator.chapters_dir / selected_file
        if file_path.exists():
            draft_to_review = file_path.read_text(encoding="utf-8")
            review_title = selected_file.removesuffix(".md")

    saved_plot_outline = generator.ctx.get_plot_outline()
    review_use_plot = st.checkbox(
        "저장한 대형 플롯을 이번 검수에 반영",
        value=False,
        key="review_use_plot",
        disabled=not bool(saved_plot_outline),
    )
    review_plot_strength = st.selectbox(
        "플롯 반영 강도",
        options=["loose", "balanced", "strict"],
        index=1,
        key="review_plot_strength",
        disabled=not review_use_plot,
        help="loose: 참고만 / balanced: 권장 / strict: 플롯 우선",
    )
    if not saved_plot_outline:
        st.caption("저장한 플롯이 없어 검수용 플롯 반영 옵션은 비활성화되어 있습니다. [1] 프로젝트 통합 설정 > 대형 플롯에서 먼저 생성해 주세요.")

    if draft_to_review:
        st.subheader("검수 대상 원고")
        edited_draft_to_review = st.text_area(
            "이 내용을 기준으로 검수를 요청합니다.",
            value=draft_to_review,
            height=300,
        )

        if st.button("현재 원고 검수 요청", type="primary"):
            report = run_with_status(
                lambda: reviewer.review_chapter(
                    edited_draft_to_review,
                    include_plot=review_use_plot,
                    plot_strength=review_plot_strength,
                ),
                "원고를 검토하는 중입니다...",
                llm_error_prefix="검수 중 오류가 발생했습니다",
                error_prefix="검수 중 예상치 못한 오류가 발생했습니다",
            )
            if report is not None:
                st.session_state["review_report"] = report
                st.session_state["reviewing_draft"] = edited_draft_to_review
                st.session_state["reviewing_title"] = review_title
                st.session_state["review_report_use_plot"] = review_use_plot
                st.session_state["review_report_plot_strength"] = review_plot_strength
                st.session_state.pop("revised_draft", None)
                st.session_state.pop("edited_revised_draft", None)

    if "review_report" in st.session_state:
        st.divider()
        st.subheader("검수 리포트")
        st.markdown(st.session_state["review_report"])

        save_col, folder_col = st.columns([1, 2])
        with save_col:
            if st.button("리포트 저장(.md)", key="save_report_btn"):
                base_title = st.session_state.get("reviewing_title", "원고")
                save_markdown_document_and_notify(
                    generator,
                    filename_title=base_title + "_검수리포트",
                    content=st.session_state["review_report"],
                    error_prefix="리포트 저장 중 오류가 발생했습니다",
                    success_prefix="리포트를 저장했습니다",
                )
        with folder_col:
            if st.button("저장 폴더 열기", key="open_folder_report"):
                open_folder(generator.chapters_dir)

        st.divider()
        st.subheader("리포트 반영")
        if st.button("리포트를 반영한 수정본 생성", type="primary"):
            report_use_plot = bool(st.session_state.get("review_report_use_plot", False))
            report_plot_strength = str(st.session_state.get("review_report_plot_strength", "balanced"))
            revised = run_with_status(
                lambda: reviewer.revise_draft(
                    st.session_state.get("reviewing_draft", draft_to_review),
                    st.session_state["review_report"],
                    include_plot=report_use_plot,
                    plot_strength=report_plot_strength,
                ),
                "검수 피드백을 반영한 수정본을 생성하는 중입니다...",
                llm_error_prefix="수정본 생성 중 오류가 발생했습니다",
                error_prefix="수정본 생성 중 예상치 못한 오류가 발생했습니다",
                success_message="수정본 생성이 완료되었습니다.",
            )
            if revised is not None:
                st.session_state["revised_draft"] = revised
                st.session_state["edited_revised_draft"] = revised

    if "revised_draft" not in st.session_state:
        return

    st.divider()
    st.subheader("수정본")
    st.text_area(
        "수정 가능한 최종본",
        height=400,
        **build_session_bound_text_area_kwargs(
            "edited_revised_draft",
            st.session_state["revised_draft"],
            st.session_state,
        ),
    )

    save_col, folder_col = st.columns([1, 2])
    with save_col:
        save_revised_btn = st.button("수정본 저장(.md)")
    with folder_col:
        if st.button("저장 폴더 열기", key="open_folder_3"):
            open_folder(generator.chapters_dir)

    if save_revised_btn:
        base_title = st.session_state.get("reviewing_title", "수정할 원고")
        save_chapter_and_notify(
            generator,
            title=base_title + "_수정본",
            content=st.session_state["edited_revised_draft"],
            error_prefix="수정본 저장 중 오류가 발생했습니다",
            success_prefix="수정본을 저장했습니다",
            summary_failure_prefix="수정본 저장",
        )

    if "revised_draft" in st.session_state:
        st.divider()
        st.subheader("컨텍스트 제안")
        st.caption("수정본을 기준으로 다음 회차용 STATE와 누적 PREVIOUS SUMMARY 제안을 만들 수 있습니다.")

        if st.button("수정본 기준 컨텍스트 제안 생성", key="review_generate_context", use_container_width=True):
            context_result = run_with_status(
                lambda: generator.build_context_suggestions(st.session_state["edited_revised_draft"]),
                "STATE/PREVIOUS SUMMARY 제안을 생성하는 중입니다...",
                llm_error_prefix="컨텍스트 제안 생성 중 오류가 발생했습니다",
                error_prefix="컨텍스트 제안 생성 중 예상치 못한 오류가 발생했습니다",
            )
            if context_result is not None:
                st.session_state["review_context_result"] = context_result
                st.session_state.pop("review_context_state", None)
                st.session_state.pop("review_context_summary", None)

        review_context_result = st.session_state.get("review_context_result", {})
        if review_context_result:
            if review_context_result.get("state_error"):
                st.warning(f"STATE 제안 생성에 실패했습니다: {review_context_result['state_error']}")
            if review_context_result.get("summary_error"):
                st.warning(f"PREVIOUS SUMMARY 제안 생성에 실패했습니다: {review_context_result['summary_error']}")

            current_snapshot = generator.ctx.get_workspace_settings()
            review_defaults = build_chapter_context_defaults(
                suggested_state=review_context_result.get("new_state", ""),
                suggested_summary=review_context_result.get("new_summary", ""),
                current_snapshot=current_snapshot,
            )

            state_col, summary_col = st.columns(2)
            with state_col:
                review_state = st.text_area(
                    "검토 후 반영할 CURRENT STATE",
                    value=review_defaults["state"],
                    height=200,
                    key="review_context_state",
                )
            with summary_col:
                review_summary = st.text_area(
                    "검토 후 반영할 PREVIOUS SUMMARY",
                    value=review_defaults["summary_of_previous"],
                    height=200,
                    key="review_context_summary",
                )

            if st.button("프로젝트 컨텍스트에 반영", key="apply_review_context", use_container_width=True):
                persist_chapter_context_update(
                    generator.ctx,
                    state=review_state,
                    summary_of_previous=review_summary,
                )
                st.success("STATE와 PREVIOUS SUMMARY를 반영했습니다.")


def render_auto_mode_tab(app: Any) -> None:
    generator = app.generator
    automator = app.automator

    st.header("반자동 연재 모드")
    st.markdown("한 번의 실행으로 초안 생성, 검수, 수정, 저장, 이전 줄거리 요약 갱신까지 처리합니다.")
    auto_step = {"READY": 0, "RUNNING": 1, "REVIEW": 2}.get(st.session_state.get("auto_state", "READY"), 0)
    render_workflow_steps(("지시사항 입력", "파이프라인 실행", "상태 저장"), auto_step)

    if "auto_state" not in st.session_state:
        st.session_state["auto_state"] = "READY"

    if st.session_state["auto_state"] == "READY":
        st.info("다음 회차의 지시사항과 제목, 분량을 입력해 주세요.")
        auto_instruction = st.text_area(
            "이번 회차 전개 지시사항",
            value="주인공이 뜻밖의 조력자를 만나고 새로운 갈등의 단서를 발견하는 장면을 구성해 주세요.",
            height=150,
            key="auto_inst",
        )
        st.text_input("회차 제목 (저장 파일명)", value="3화 새로운 조짐", key="auto_title")
        st.number_input("생성 분량(글자수 목표)", min_value=500, max_value=20000, value=5000, step=500, key="auto_len")

        saved_plot_outline = generator.ctx.get_plot_outline()
        auto_use_plot = st.checkbox(
            "저장한 대형 플롯을 이번 반자동 파이프라인에 반영",
            value=False,
            key="auto_use_plot",
            disabled=not bool(saved_plot_outline),
        )
        st.selectbox(
            "플롯 반영 강도",
            options=["loose", "balanced", "strict"],
            index=1,
            key="auto_plot_strength",
            disabled=not auto_use_plot,
            help="loose: 참고만 / balanced: 권장 / strict: 플롯 우선",
        )
        if not saved_plot_outline:
            st.caption("저장한 플롯이 없어 플롯 반영 옵션은 비활성화되어 있습니다. [1] 프로젝트 통합 설정 > 대형 플롯에서 먼저 생성해 주세요.")

        if st.button("반자동 파이프라인 실행", type="primary", use_container_width=True):
            if not ensure_api_key():
                pass
            elif not auto_instruction.strip():
                st.warning("지시사항을 입력해 주세요.")
            else:
                st.session_state["auto_state"] = "RUNNING"
                st.rerun()

    elif st.session_state["auto_state"] == "RUNNING":
        st.info("파이프라인을 실행 중입니다. 잠시만 기다려 주세요.")
        try:
            result = automator.run_single_cycle(
                st.session_state["auto_title"],
                st.session_state["auto_inst"],
                st.session_state["auto_len"],
                include_plot=bool(st.session_state.get("auto_use_plot", False)),
                plot_strength=str(st.session_state.get("auto_plot_strength", "balanced")),
                step_context=st.spinner,
            )
            st.session_state["auto_result"] = result
            st.session_state["auto_state"] = "REVIEW"
            st.rerun()
        except Exception as exc:
            st.error(f"파이프라인 실행 중 오류가 발생했습니다: {exc}")
            if st.button("돌아가기"):
                st.session_state["auto_state"] = "READY"
                st.rerun()

    elif st.session_state["auto_state"] == "REVIEW":
        st.success("반자동 실행이 완료되었습니다. 다음 회차용 상태만 확인하고 저장하면 됩니다.")

        result = st.session_state.get("auto_result", {})
        if result.get("state_error"):
            st.warning(f"STATE 제안 생성에 실패했습니다: {result['state_error']}")
        if result.get("summary_error"):
            st.warning(f"이전 줄거리 요약 갱신은 실패했습니다: {result['summary_error']}")

        with st.expander("[결과] 생성된 초안", expanded=False):
            st.text_area("초안", value=result.get("draft", ""), height=300)
            if result.get("draft_path"):
                st.info(f"초안 저장 위치: `{result['draft_path']}`")

        with st.expander("[결과] 수정본", expanded=False):
            st.text_area("수정본", value=result.get("revised_draft", ""), height=400)
            if result.get("saved_path"):
                st.info(f"최종 저장 위치: `{result['saved_path']}`")

        with st.expander("[결과] 검수 리포트", expanded=False):
            st.markdown(result.get("review_report", ""))
            if result.get("review_report_path"):
                st.info(f"리포트 저장 위치: `{result['review_report_path']}`")

        st.divider()
        st.subheader("다음 회차용 상태 갱신")
        st.markdown("방금 생성한 결과를 바탕으로 `STATE`와 `PREVIOUS SUMMARY`를 검토한 뒤 저장해 주세요.")

        current_snapshot = generator.ctx.get_workspace_settings()
        auto_defaults = build_chapter_context_defaults(
            suggested_state=result.get("new_state", ""),
            suggested_summary=result.get("new_summary", ""),
            current_snapshot=current_snapshot,
        )
        state_col, summary_col = st.columns(2)
        with state_col:
            new_state = st.text_area(
                "CURRENT STATE 업데이트",
                value=auto_defaults["state"],
                height=200,
                help="현재 갈등과 다음 회차 목표를 최신 상태로 정리해 주세요.",
            )
        with summary_col:
            new_summary = st.text_area(
                "PREVIOUS SUMMARY",
                value=auto_defaults["summary_of_previous"],
                height=200,
                help="자동 갱신 결과를 검토하고 필요하면 수정해 주세요.",
            )

        st.divider()
        if st.button("상태 저장 후 READY로 전환", type="primary", use_container_width=True):
            persist_chapter_context_update(
                generator.ctx,
                state=new_state,
                summary_of_previous=new_summary,
            )

            for key in ["auto_result", "auto_title", "auto_inst", "auto_len"]:
                st.session_state.pop(key, None)
            st.session_state["auto_state"] = "READY"

            st.success("상태를 저장했습니다. 다음 회차를 준비할 수 있습니다.")
            st.rerun()
