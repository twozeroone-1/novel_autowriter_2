import os

from core.llm import LLMError, _extract_first_json_value, generate_text


DEFAULT_CRITIC_REPORT = {
    "status": "critic_unavailable",
    "summary": "",
    "issues": [],
    "model": "",
    "cost": {"mode": "single_pass"},
    "raw_excerpt": "",
}


def _has_meaningful_episode_plan(episode_plan: dict | None) -> bool:
    if not isinstance(episode_plan, dict):
        return False

    scalar_fields = (
        "episode_objective",
        "tone_notes",
    )
    list_fields = (
        "must_include_characters",
        "hooks_to_payoff",
        "hooks_to_advance",
        "forbidden_moves",
        "continuity_focus",
    )
    if any(str(episode_plan.get(field, "") or "").strip() for field in scalar_fields):
        return True
    for field in list_fields:
        value = episode_plan.get(field, [])
        if isinstance(value, list) and any(str(item or "").strip() for item in value):
            return True
    return False


def _build_critic_prompt(final_source: dict, episode_plan: dict | None) -> str:
    title = str(final_source.get("title", "")).strip()
    content = str(final_source.get("content", "")).strip()
    plan = episode_plan if isinstance(episode_plan, dict) else {}
    return f"""당신은 웹소설 발행 직전 최종 품질 비평가입니다.
다음 회차 원고가 실제 발행 가능한 수준인지 판단하세요.

[EPISODE PLAN]
{plan}

[EPISODE TITLE]
{title}

[EPISODE BODY]
{content}

[OUTPUT RULES]
- JSON object 하나만 반환
- status는 passed 또는 blocked 중 하나
- summary는 한 줄
- issues는 문자열 배열
"""


def _normalize_critic_payload(payload: dict | None, *, raw_text: str) -> dict:
    report = {
        "status": "critic_unavailable",
        "summary": "",
        "issues": [],
        "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        "cost": {"mode": "single_pass"},
        "raw_excerpt": raw_text[:400],
    }
    if not isinstance(payload, dict):
        report["summary"] = "critic returned invalid json"
        return report

    status = str(payload.get("status", "")).strip().lower()
    if status not in {"passed", "blocked"}:
        report["summary"] = "critic returned invalid status"
        return report

    issues = payload.get("issues", [])
    if isinstance(issues, str):
        issues = [issues]
    if not isinstance(issues, list):
        issues = []

    report["status"] = status
    report["summary"] = str(payload.get("summary", "")).strip()
    report["issues"] = [str(item).strip() for item in issues if str(item).strip()]
    return report


def evaluate_publish_critic(final_source: dict, *, episode_plan: dict | None = None) -> dict:
    if not _has_meaningful_episode_plan(episode_plan):
        report = dict(DEFAULT_CRITIC_REPORT)
        report["status"] = "passed"
        report["summary"] = "critic skipped: no episode plan"
        report["model"] = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        return report

    prompt = _build_critic_prompt(final_source, episode_plan)
    try:
        raw_text = generate_text(
            prompt,
            system_instruction="너는 발행 가능한 회차와 발행하면 안 되는 회차를 냉정하게 구분하는 웹소설 critic이다.",
            temperature=0.2,
            feature="publish_critic",
        )
    except LLMError as exc:
        report = dict(DEFAULT_CRITIC_REPORT)
        report["summary"] = str(exc)
        report["model"] = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        return report

    payload = _extract_first_json_value(raw_text, expected_type=dict)
    return _normalize_critic_payload(payload, raw_text=raw_text)
