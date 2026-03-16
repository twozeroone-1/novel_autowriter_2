import json
from copy import deepcopy

from core.canon_store import CanonStore
from core.context_state_store import ContextStateStore
from core.llm import _extract_first_json_value, generate_text
from core.plot_store import PlotStore
from core.publishing_store import PublishingStore
from core.release_policy_store import ReleasePolicyStore
from core.story_bible_store import StoryBibleStore


DEFAULT_EPISODE_PLAN = {
    "episode_objective": "",
    "must_include_characters": [],
    "hooks_to_payoff": [],
    "hooks_to_advance": [],
    "forbidden_moves": [],
    "target_length": 5000,
    "tone_notes": "",
    "continuity_focus": [],
    "plan_version": "v1",
}


def _normalize_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if not isinstance(value, list):
        return []

    normalized: list[str] = []
    for item in value:
        if item is None:
            continue
        text = item if isinstance(item, str) else str(item)
        if text.strip():
            normalized.append(text)
    return normalized


class EpisodePlanner:
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.story_bible_store = StoryBibleStore(project_name=project_name)
        self.canon_store = CanonStore(project_name=project_name)
        self.context_state_store = ContextStateStore(project_name=project_name)
        self.plot_store = PlotStore(project_name=project_name)
        self.release_policy_store = ReleasePolicyStore(project_name=project_name)
        self.publishing_store = PublishingStore(project_name=project_name)

    def _build_planner_prompt(
        self,
        *,
        instruction: str,
        length_goal: int,
        include_plot: bool,
        plot_strength: str,
    ) -> str:
        story_bible = self.story_bible_store.load()
        canon_state = self.canon_store.load_current_state()
        context_state = self.context_state_store.load()
        release_policy = self.release_policy_store.load()
        recent_history = self.publishing_store.load_recent_history(limit=5)
        sections = [
            "[STORY BIBLE]",
            json.dumps(
                {
                    "worldview": story_bible.get("worldview", ""),
                    "style_guide": story_bible.get("style_guide", ""),
                    "fixed_rules": story_bible.get("fixed_rules", ""),
                },
                ensure_ascii=False,
                indent=2,
            ),
            "",
            "[CANON FACTS]",
            json.dumps(canon_state, ensure_ascii=False, indent=2),
            "",
            "[STATE]",
            json.dumps(context_state, ensure_ascii=False, indent=2),
            "",
            "[RELEASE POLICY]",
            json.dumps(release_policy, ensure_ascii=False, indent=2),
            "",
            "[RECENT PUBLISH HISTORY]",
            json.dumps(recent_history, ensure_ascii=False, indent=2),
        ]
        if include_plot:
            plot_payload = self.plot_store.load()
            plot_outline = str(plot_payload.get("plot_outline", "")).strip()
            if plot_outline:
                sections.extend(
                    [
                        "",
                        "[PLOT OUTLINE]",
                        plot_outline,
                        "",
                        "[PLOT STRENGTH]",
                        str(plot_strength),
                    ]
                )
        sections.extend(
            [
                "",
                "[USER INSTRUCTION]",
                str(instruction),
                "",
                "[OUTPUT RULES]",
                "- JSON object 하나만 반환할 것",
                "- 새 canon 사실을 만들지 말 것",
                "- 산문을 쓰지 말고 계획만 출력할 것",
                f"- target_length는 기본적으로 {length_goal}를 사용",
                (
                    '- 필수 키: "episode_objective", "must_include_characters", '
                    '"hooks_to_payoff", "hooks_to_advance", "forbidden_moves", '
                    '"target_length", "tone_notes", "continuity_focus", "plan_version"'
                ),
            ]
        )
        return "\n".join(sections)

    def _normalize_plan_payload(self, payload: dict | list | None, *, length_goal: int) -> dict:
        normalized = deepcopy(DEFAULT_EPISODE_PLAN)
        normalized["target_length"] = int(length_goal)
        if not isinstance(payload, dict):
            return normalized

        episode_objective = payload.get("episode_objective", "")
        if episode_objective is not None:
            normalized["episode_objective"] = str(episode_objective).strip()

        tone_notes = payload.get("tone_notes", "")
        if tone_notes is not None:
            normalized["tone_notes"] = str(tone_notes).strip()

        target_length = payload.get("target_length", length_goal)
        try:
            normalized["target_length"] = int(target_length)
        except (TypeError, ValueError):
            normalized["target_length"] = int(length_goal)

        plan_version = payload.get("plan_version", "v1")
        normalized["plan_version"] = str(plan_version).strip() or "v1"

        for field in (
            "must_include_characters",
            "hooks_to_payoff",
            "hooks_to_advance",
            "forbidden_moves",
            "continuity_focus",
        ):
            normalized[field] = _normalize_string_list(payload.get(field))
        return normalized

    def build_episode_plan(
        self,
        instruction: str,
        *,
        length_goal: int,
        include_plot: bool,
        plot_strength: str = "balanced",
    ) -> dict:
        prompt = self._build_planner_prompt(
            instruction=instruction,
            length_goal=length_goal,
            include_plot=include_plot,
            plot_strength=plot_strength,
        )
        raw_text = generate_text(
            prompt,
            system_instruction="너는 웹소설 한 회차의 서사 목적을 구조화하는 에피소드 플래너다.",
            temperature=0.2,
            project_name=self.project_name,
            feature="episode_plan",
        )
        parsed = _extract_first_json_value(raw_text, expected_type=dict)
        return self._normalize_plan_payload(parsed, length_goal=length_goal)
