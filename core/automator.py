from contextlib import nullcontext
from typing import Any, Callable

from core.generator import Generator
from core.reviewer import Reviewer


class Automator:
    def __init__(
        self,
        project_name: str = "default_project",
        generator: Generator | None = None,
        reviewer: Reviewer | None = None,
    ):
        self.project_name = project_name
        self.generator = generator or Generator(project_name=project_name)
        self.reviewer = reviewer or Reviewer(project_name=project_name)

    def run_single_cycle(
        self,
        chapter_title: str,
        instruction: str,
        target_length: int = 5000,
        include_plot: bool = False,
        plot_strength: str = "balanced",
        step_context: Callable[[str], Any] | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        progress = step_context or (lambda _message: nullcontext())

        with progress(f"초안 생성 중입니다 (목표: {target_length}자 내외)..."):
            draft = self.generator.create_chapter(
                instruction,
                target_length,
                include_plot=include_plot,
                plot_strength=plot_strength,
            )
            result["draft"] = draft

        with progress("초안을 마크다운 파일로 저장 중입니다..."):
            result["draft_path"] = self.generator.save_markdown_document(
                filename_title=chapter_title + "_초안",
                content=draft,
                heading_title=chapter_title + " (초안)",
            )

        with progress("검수 리포트를 생성 중입니다..."):
            review_report = self.reviewer.review_chapter(
                draft,
                include_plot=include_plot,
                plot_strength=plot_strength,
            )
            result["review_report"] = review_report

        with progress("검수 리포트를 저장 중입니다..."):
            result["review_report_path"] = self.generator.save_markdown_document(
                filename_title=chapter_title + "_검수리포트",
                content=review_report,
            )

        with progress("검수 피드백을 반영한 수정본을 생성 중입니다..."):
            revised_draft = self.reviewer.revise_draft(
                draft,
                review_report,
                include_plot=include_plot,
                plot_strength=plot_strength,
            )
            result["revised_draft"] = revised_draft

        with progress("수정본을 저장 중입니다..."):
            saved_bundle = self.generator.save_chapter_bundle(chapter_title, revised_draft)
            result["saved_path"] = saved_bundle["path"]
            episode = saved_bundle.get("episode", {}) if isinstance(saved_bundle, dict) else {}
            episode_id = str(episode.get("episode_id", "")).strip() if isinstance(episode, dict) else ""
            if episode_id:
                result["episode_id"] = episode_id

        with progress("다음 회차용 STATE/PREVIOUS SUMMARY 제안을 생성 중입니다..."):
            result.update(self.generator.build_context_suggestions(revised_draft))

        with progress("구조화 Canon 후보를 추출 중입니다..."):
            try:
                canon_update = self.generator.build_canon_update_candidate(revised_draft)
                result["canon_update"] = canon_update
                if episode_id:
                    self.generator.artifact_store.save_canon_update(episode_id, canon_update)
            except Exception as exc:
                result["canon_update_error"] = str(exc)

        return result

    def apply_context_updates(
        self,
        *,
        state: str | None = None,
        summary_of_previous: str | None = None,
    ) -> dict[str, Any]:
        return self.generator.ctx.apply_context_updates(
            state=state,
            summary_of_previous=summary_of_previous,
        )
