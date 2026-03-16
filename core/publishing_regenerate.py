import json

from core.llm import _extract_first_json_value, generate_text


def _build_regeneration_prompt(
    source_payload: dict,
    *,
    episode_plan: dict | None,
    length_goal: int | None,
) -> str:
    source_title = str(source_payload.get("title", "")).strip()
    source_content = str(source_payload.get("content", "")).strip()
    normalized_plan = episode_plan if isinstance(episode_plan, dict) else {}
    target_length = int(length_goal or normalized_plan.get("target_length") or 5000)
    return "\n".join(
        [
            "[EPISODE PLAN]",
            json.dumps(normalized_plan, ensure_ascii=False, indent=2),
            "",
            "[CURRENT SOURCE]",
            json.dumps(
                {
                    "title": source_title,
                    "content": source_content,
                },
                ensure_ascii=False,
                indent=2,
            ),
            "",
            "[OUTPUT RULES]",
            "- 같은 episode_plan을 유지할 것",
            "- 회차 번호를 바꾸지 말 것",
            f"- 목표 분량은 약 {target_length}자 내외로 유지할 것",
            '- JSON object 하나만 반환할 것: "title", "content", "regeneration_summary"',
        ]
    )


def _normalize_regeneration_payload(payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        return {
            "status": "failed",
            "reason": "regeneration returned invalid json",
            "title": "",
            "content": "",
            "regeneration_summary": "",
        }

    title = str(payload.get("title", "")).strip()
    content = str(payload.get("content", "")).strip()
    summary = str(payload.get("regeneration_summary", "")).strip()
    if not title or not content:
        return {
            "status": "failed",
            "reason": "regeneration returned incomplete payload",
            "title": "",
            "content": "",
            "regeneration_summary": summary,
        }
    return {
        "status": "applied",
        "reason": "",
        "title": title,
        "content": content,
        "regeneration_summary": summary,
    }


def regenerate_publish_source(
    source_payload: dict,
    *,
    episode_plan: dict | None,
    project_name: str | None = None,
    length_goal: int | None = None,
) -> dict:
    prompt = _build_regeneration_prompt(
        source_payload,
        episode_plan=episode_plan,
        length_goal=length_goal,
    )
    try:
        raw_text = generate_text(
            prompt,
            system_instruction="너는 웹소설 발행 후보 원고를 같은 회차 계획으로 한 번만 다시 쓰는 품질 재생성기다.",
            temperature=0.3,
            project_name=project_name,
            feature="publish_regenerate",
        )
    except Exception as exc:
        return {
            "status": "failed",
            "reason": str(exc).strip() or "regeneration backend failed",
            "title": "",
            "content": "",
            "regeneration_summary": "",
        }
    payload = _extract_first_json_value(raw_text, expected_type=dict)
    return _normalize_regeneration_payload(payload)
