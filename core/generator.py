import json
import re
from datetime import datetime
from pathlib import Path
from core.canon_extractor import extract_canon_update
from core.episode_planner import DEFAULT_EPISODE_PLAN, EpisodePlanner
from core.episode_artifact_store import EpisodeArtifactStore
from core.file_utils import atomic_write_text
from core.llm import _extract_first_json_value, generate_text
from core.run_snapshot_store import RunSnapshotStore
from core.context import ContextManager

class Generator:
    def __init__(self, project_name: str = "default_project"):
        # ContextManager에 project_name 주입
        self.ctx = ContextManager(project_name=project_name)
        self.episode_planner = EpisodePlanner(project_name=project_name)
        self.artifact_store = EpisodeArtifactStore(project_name=project_name)
        self.snapshot_store = RunSnapshotStore(project_name=project_name)
        # ContextManager가 생성한 동적 경로를 참조
        self.chapters_dir = self.ctx.data_dir / "chapters"
        self.chapters_dir.mkdir(parents=True, exist_ok=True)

    def _build_fallback_episode_plan(self, *, length_goal: int, planner_error: str | None = None) -> dict:
        plan = dict(DEFAULT_EPISODE_PLAN)
        plan["target_length"] = int(length_goal)
        if planner_error:
            plan["planner_error"] = planner_error
        return plan
        
    def create_chapter(
        self,
        instruction: str,
        length_goal: int = 5000,
        include_plot: bool = False,
        plot_strength: str = "balanced",
    ) -> str:
        """컨텍스트를 모아 LLM에 전달하고 생성된 원고 텍스트를 반환합니다."""
        run_id = self.snapshot_store.create_run_id(prefix="chapter")
        try:
            episode_plan = self.episode_planner.build_episode_plan(
                instruction,
                length_goal=length_goal,
                include_plot=include_plot,
                plot_strength=plot_strength,
            )
        except Exception as exc:
            episode_plan = self._build_fallback_episode_plan(
                length_goal=length_goal,
                planner_error=str(exc),
            )
        self.snapshot_store.write_json_snapshot(run_id, "episode_plan.json", episode_plan)
        prompt = self.ctx.build_generation_prompt(
            instruction,
            length_goal,
            include_plot=include_plot,
            plot_strength=plot_strength,
            episode_plan=episode_plan,
        )
        print(f">> [{self.ctx.project_name}] 작품 생성 요청 중...")
        system_instruction = f"너는 사용자가 제시한 목표 분량(공백 포함 약 {length_goal}자 내외)을 엄격하게 지키으면서 기승전결이 있는 전개를 작성하는 프로 웹소설 작가야."
        result = generate_text(
            prompt,
            system_instruction=system_instruction,
            project_name=self.ctx.project_name,
            feature="chapter_generate",
        )
        return result
        
    def save_chapter(self, title: str, content: str) -> str:
        """생성된 회차를 마크다운 파일로 저장합니다."""
        return self.save_chapter_bundle(title, content)["path"]

    def save_chapter_bundle(self, title: str, content: str) -> dict:
        return self._save_markdown_document(
            filename_title=title,
            content=content,
            heading_title=title,
            persist_episode_artifact=True,
        )

    def save_markdown_document(
        self,
        filename_title: str,
        content: str,
        heading_title: str | None = None,
    ) -> str:
        """안전한 파일명으로 마크다운 문서를 저장합니다."""
        return self._save_markdown_document(
            filename_title=filename_title,
            content=content,
            heading_title=heading_title,
            persist_episode_artifact=False,
        )["path"]

    def _save_markdown_document(
        self,
        filename_title: str,
        content: str,
        heading_title: str | None = None,
        *,
        persist_episode_artifact: bool,
    ) -> dict:
        filepath = self.build_output_path(filename_title, ".md")
        markdown_text = content
        if heading_title:
            markdown_text = f"# {heading_title}\n\n{content}"
        atomic_write_text(filepath, markdown_text)
        artifact = None
        if filepath.suffix == ".md" and persist_episode_artifact:
            artifact_title = heading_title or filename_title
            artifact = self.artifact_store.create_draft(title=artifact_title, content=markdown_text)
        return {
            "path": str(filepath),
            "artifact": artifact,
        }

    def build_output_path(self, title: str, suffix: str = ".md") -> Path:
        """제목을 안전한 파일명으로 바꿔 중복 없는 출력 경로를 만듭니다."""
        safe_title = self._build_safe_title(title)
        if not safe_title:
            safe_title = "연재_" + datetime.now().strftime("%Y%m%d%H%M%S")
        return self._build_unique_filepath(safe_title, suffix)

    def _build_safe_title(self, title: str) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", title)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
        cleaned = cleaned.replace(":", " ")
        return cleaned

    def _build_unique_filepath(self, safe_title: str, suffix: str) -> Path:
        candidate = self.chapters_dir / f"{safe_title}{suffix}"
        if not candidate.exists():
            return candidate

        counter = 2
        while True:
            candidate = self.chapters_dir / f"{safe_title}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
        
    def summarize_chapter(self, chapter_content: str) -> str:
        """작성된 회차의 핵심 내용을 짧게 요약합니다."""
        prompt = f"""당신은 웹소설 편집자입니다. 방금 작성된 다음 원고를 읽고, 이후 스토리 전개에 참고할 수 있도록 주요 사건과 인물의 감정선/변화를 3~4줄로 핵심만 요약해 주세요.

[원고 내용]
{chapter_content}

요약:"""
        print(">> 회차 요약 생성 중...")
        result = generate_text(prompt, system_instruction="너는 줄거리 파악과 요약에 능통한 편집자야.")
        return result.strip()

    def summarize_and_update_context(self, chapter_content: str) -> str:
        new_summary = self.summarize_chapter(chapter_content)
        self.ctx.update_summary(new_summary, generator_instance=self)
        return new_summary

    def build_summary_update_preview(self, chapter_content: str) -> str:
        new_summary = self.summarize_chapter(chapter_content)
        return self.ctx.build_updated_summary_text(new_summary, generator_instance=self)

    def build_context_suggestions(self, chapter_content: str) -> dict[str, str]:
        suggestions: dict[str, str] = {}
        try:
            suggestions["new_state"] = self.summarize_state(chapter_content)
        except Exception as exc:
            suggestions["state_error"] = str(exc)

        try:
            suggestions["new_summary"] = self.build_summary_update_preview(chapter_content)
        except Exception as exc:
            suggestions["summary_error"] = str(exc)

        return suggestions

    def build_canon_update_candidate(self, chapter_content: str) -> dict:
        return extract_canon_update(chapter_content, project_name=self.ctx.project_name)

    def compress_history_summary(self, long_summary: str) -> str:
        """누적된 과거 줄거리가 너무 길어지면 이를 계층형(시즌 요약 + 최근 전개)으로 초압축합니다."""
        prompt = f"""당신은 탑티어 웹소설 편집자입니다.
다음은 현재까지 연재된 소설의 방대한 누적 줄거리 요약본입니다. 이 내용이 너무 길어져 압축이 필요합니다.

[기존 누적 줄거리]
{long_summary}

위 텍스트를 읽고 다음 두 가지 파트로 나누어 새롭게 요약해 주세요.
1. [시즌 요약]: 극초반부부터 중간부까지의 전반적인 핵심 기승전 흐름을 500자 이내의 단일 문단으로 초압축하세요.
2. [최근 전개]: 기존 요약본의 가장 맨 마지막 부분(최근 3~4화 분량)에 해당하는 구체적인 사건 전개와 떡밥, 감정선은 디테일을 살려서 300자 이내로 요약해 주세요.

반드시 아래와 같은 포맷으로만 출력하세요.
[시즌 요약]
(여기에 시즌 요약 내용)

[최근 전개]
(여기에 최근 전개 내용)
"""
        print(">> ⚠️ 토큰 최적화: 방대한 과거 줄거리 압축 진행 중...")
        result = generate_text(prompt, system_instruction="너는 방대한 스토리를 구조적으로 완벽하게 요약하는 편집자야.")
        return result.strip()

    def elaborate_worldview(self, draft_content: str) -> str:
        """사용자가 입력한 세계관 초안을 바탕으로 AI가 구체적인 세계관을 생성합니다."""
        prompt = f"""당신은 탑티어 웹소설 세계관 기획자입니다.
작가가 구상한 다음 '세계관 초안'을 바탕으로, 독자들이 흥미를 느낄 만한 구체적이고 매력적인 세계관 설정(배경, 마법/기연/시스템 체계, 주요 세력이나 갈등 요소 등)으로 디테일을 더해주세요.

[세계관 초안]
{draft_content}

너무 장황하지 않게 4~6개 핵심 항목 중심으로 정리해 주세요.
- 설정을 새로 과도하게 발명하지 말 것
- 독자가 바로 이해할 수 있는 수준으로 명확하게 쓸 것
- 총 분량은 700자 이내로 제한할 것"""
        print(">> 세계관 구체화 중...")
        result = generate_text(prompt, system_instruction="너는 상상력이 풍부하고 체계적인 세계관 기획자야.")
        return result.strip()

    def compress_worldview(self, draft_content: str) -> str:
        """세계관 텍스트를 더 짧고 선명한 설정 문서로 압축합니다."""
        prompt = f"""다음 STORY BIBLE 초안을 작가 작업용 핵심 설정 문서로 압축해 주세요.

[원본 STORY BIBLE]
{draft_content}

[요구사항]
- 핵심만 남길 것
- 5~8개 항목 이내
- 각 항목은 짧은 문장 1~2개
- 배경/핵심 규칙/주요 갈등/주인공 목표 중심
- 새 설정을 지어내지 말고 원문 정보만 재정리할 것"""
        print(">> 세계관 압축 정리 중...")
        result = generate_text(prompt, system_instruction="너는 긴 설정 문서를 짧고 선명하게 정리하는 편집자야.")
        return result.strip()

    def structure_style_guide(self, draft_content: str) -> str:
        """문체 지침 초안을 짧은 규칙 목록으로 정리합니다."""
        prompt = f"""다음 STYLE GUIDE 초안을 실제 집필에 바로 쓸 수 있는 규칙 목록으로 정리해 주세요.

[원본 STYLE GUIDE]
{draft_content}

[출력 조건]
- 6~10개 규칙
- 각 규칙은 한 줄
- 시점, 문장 길이, 대사 비율, 묘사 밀도, 금지 표현, 감정선 처리 우선
- 새 취향을 덧붙이지 말고 원문 의도만 정리할 것"""
        print(">> 문체 지침 정리 중...")
        result = generate_text(prompt, system_instruction="너는 작가의 문체 요구를 짧은 규칙집으로 정리하는 에디터야.")
        return result.strip()

    def structure_continuity(self, draft_content: str) -> str:
        """CONTINUITY 초안을 불변 규칙 중심으로 재정리합니다."""
        prompt = f"""다음 CONTINUITY 초안을 고정 설정 문서로 재정리해 주세요.

[원본 CONTINUITY]
{draft_content}

[출력 형식]
[절대 불변 규칙]
- ...

[연표/사실]
- ...

[관계/상태]
- ...

[주의사항]
- 새 설정을 추가하지 말 것
- 모호한 문장은 짧고 단정적으로 다듬을 것
- 전체 길이는 500자 안팎으로 제한할 것"""
        print(">> 고정 설정 정리 중...")
        result = generate_text(prompt, system_instruction="너는 설정 충돌을 막기 위해 고정 규칙만 선명하게 정리하는 편집자야.")
        return result.strip()

    def summarize_state(self, draft_content: str) -> str:
        """STATE 초안을 현재 진행 상태 중심으로 압축합니다."""
        prompt = f"""다음 STATE 초안을 다음 회차 집필용 현재 상황 요약으로 정리해 주세요.

[원본 STATE]
{draft_content}

[출력 형식]
[현재 갈등]
- ...

[인물 감정선]
- ...

[미해결 떡밥]
- ...

[다음 회차 목표]
- ...

[주의사항]
- 최근 상황만 남길 것
- 장기 세계관 설명은 삭제할 것
- 새 사건을 추가하지 말 것
- 전체 길이는 400자 안팎으로 제한할 것"""
        print(">> 현재 상태 요약 중...")
        result = generate_text(prompt, system_instruction="너는 장기 설정과 현재 진행 상황을 분리해 짧게 정리하는 스토리 에디터야.")
        return result.strip()

    def generate_tone(self, worldview: str) -> str:
        """세계관을 바탕으로 어울리는 소설 문체 및 분위기를 제안합니다."""
        prompt = f"""당신은 탑티어 웹소설 기획자입니다.
다음 구축된 세계관을 바탕으로 이 소설에 가장 잘 어울릴법한 '문체 및 분위기 지침(Tone & Manner)'을 2~3문장으로 작성해 주세요. 
(예시: 건조하고 속도감 있는 문체. 주인공의 냉소적인 독백을 중심으로 사건이 전개됨.)

[세계관]
{worldview}"""
        print(">> 문체 및 분위기 제안 중...")
        result = generate_text(prompt, system_instruction="너는 작품에 색깔을 입히는 웹소설 기획자야.")
        return result.strip()
        
    def _trim_recent_summary_for_characters(self, summary_text: str, max_chars: int = 1200) -> str:
        summary_text = summary_text.strip()
        if not summary_text:
            return ""
        if len(summary_text) <= max_chars:
            return summary_text

        marker = "[진행된 줄거리 요약]"
        if marker in summary_text:
            chunks = [chunk.strip() for chunk in summary_text.split(marker) if chunk.strip()]
            selected: list[str] = []
            total = 0
            for chunk in reversed(chunks):
                chunk_len = len(chunk)
                if total and total + chunk_len > max_chars:
                    break
                selected.append(chunk)
                total += chunk_len
                if total >= max_chars:
                    break
            if selected:
                recent_joined = f"\n\n{marker}\n".join(reversed(selected))
                return f"{marker}\n{recent_joined}"

        return summary_text[-max_chars:]

    def _build_character_extraction_source(
        self,
        worldview: str,
        continuity: str = "",
        state: str = "",
        summary_of_previous: str = "",
    ) -> str:
        sections = []
        if worldview.strip():
            sections.append(f"[STORY BIBLE]\n{worldview.strip()}")
        if continuity.strip():
            sections.append(f"[CONTINUITY]\n{continuity.strip()}")
        if state.strip():
            sections.append(f"[STATE]\n{state.strip()}")

        trimmed_summary = self._trim_recent_summary_for_characters(summary_of_previous)
        if trimmed_summary:
            sections.append(f"[RECENT SUMMARY]\n{trimmed_summary}")

        return "\n\n".join(sections)

    def generate_characters(
        self,
        worldview: str,
        continuity: str = "",
        state: str = "",
        summary_of_previous: str = "",
    ) -> str:
        """핵심 설정 문서들을 바탕으로 주요 등장인물 JSON 배열을 추출 및 생성합니다."""
        source_text = self._build_character_extraction_source(
            worldview=worldview,
            continuity=continuity,
            state=state,
            summary_of_previous=summary_of_previous,
        )
        prompt = f"""당신은 탑티어 웹소설 기획자입니다.
다음 프로젝트 설정 텍스트를 읽고, 텍스트 내에 실제로 언급되거나 암시된 주요 등장인물을 추출 및 기획해 주세요.
주의: 반드시 텍스트에 존재하는 인물만 추출해야 하며, 절대 새로운 인물을 창작하거나 지어내지 마세요.
우선순위:
- 명시적으로 이름이 나온 인물
- 반복적으로 등장하거나 관계/감정선이 언급된 인물
- 작품 진행에 의미가 있는 조연
제외 대상:
- 일회성 엑스트라
- 배경용 군중
- 이름 없이 잠깐 스쳐가는 인물
반드시 아래의 JSON 배열 포맷으로만 출력해야 합니다. 추가 설명이나 마크다운 백틱(```) 없이 순수 JSON 텍스트 배열만 반환하세요.

포맷 예시:
[
  {{
    "id": "char_001",
    "name": "등장인물 이름",
    "role": "주인공/조력자 등",
    "description": "성격 요약 (1문장)",
    "traits": ["강함", "과묵함"]
  }}
]

[프로젝트 설정]
{source_text}"""
        print(">> 캐릭터 설정 생성 중...")
        result = generate_text(
            prompt,
            system_instruction="너는 매력적인 캐릭터를 짜는 웹소설 기획자야. JSON 형식으로만 답해.",
            temperature=0.2,
            project_name=self.ctx.project_name,
            feature="character_extract",
        )

        extracted = _extract_first_json_value(result, expected_type=list)
        if extracted is not None:
            return json.dumps(extracted, ensure_ascii=False, indent=2)

        cleaned = result.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        return cleaned.strip()
