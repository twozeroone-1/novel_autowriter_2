import json

from core.llm import generate_text


def _extract_first_json_object(raw_text: str) -> dict | None:
    decoder = json.JSONDecoder()
    starts = [index for index, char in enumerate(raw_text) if char == "{"]
    for start in starts:
        fragment = raw_text[start:]
        try:
            value, _ = decoder.raw_decode(fragment)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def repair_publish_source(source_payload: dict, gate_reports: dict) -> dict:
    title = str(source_payload.get("title", "")).strip()
    content = str(source_payload.get("content", "")).strip()
    prompt = (
        "다음 웹소설 발행 원고를 최소 수정으로 정리해라.\n"
        "- 이야기 내용과 사건 순서는 바꾸지 마라.\n"
        "- 초안/수정본/검수 메모 같은 보조 문구를 제거하라.\n"
        "- 제목과 첫 heading 번호를 일치시켜라.\n"
        "- 새 장면을 추가하거나 요약하지 마라.\n"
        "- 반드시 JSON object 하나만 반환하라.\n"
        '- 형식: {"title": "...", "content": "..."}\n\n'
        f"[gate_reports]\n{json.dumps(gate_reports, ensure_ascii=False, indent=2)}\n\n"
        f"[title]\n{title}\n\n"
        f"[content]\n{content}\n"
    )
    raw_text = generate_text(
        prompt,
        system_instruction="너는 발행 직전 원고를 최소 수정으로 정리하는 편집자다.",
        temperature=0.1,
        feature="revise",
    )
    parsed = _extract_first_json_object(raw_text)
    if not isinstance(parsed, dict):
        return {}
    repaired_title = parsed.get("title")
    repaired_content = parsed.get("content")
    if not isinstance(repaired_title, str) or not isinstance(repaired_content, str):
        return {}
    return {
        "title": repaired_title,
        "content": repaired_content,
    }
