from core.canon_candidate import normalize_canon_candidate
from core.llm import _extract_first_json_value, generate_text


def build_canon_extraction_prompt(chapter_content: str) -> str:
    return f"""다음 웹소설 회차 본문을 읽고, 구조화된 Canon 업데이트만 JSON 객체 하나로 추출해 주세요.

[출력 규칙]
- 반드시 JSON 객체 하나만 출력
- 허용 키는 people, resources, hooks, timeline
- 새 사실이 없으면 빈 구조를 유지
- people/resources 는 객체
- hooks/timeline 은 배열
- 추측하지 말고 본문에 직접 드러난 사실만 적을 것

[회차 본문]
{chapter_content}
"""


def extract_canon_update(chapter_content: str, *, project_name: str | None = None) -> dict:
    prompt = build_canon_extraction_prompt(chapter_content)
    raw_text = generate_text(
        prompt,
        system_instruction="너는 발행된 회차에서 사실 관계만 뽑아 구조화하는 웹소설 캐논 추출기야.",
        project_name=project_name,
        feature="canon_extract",
    )
    payload = _extract_first_json_value(raw_text, expected_type=dict)
    if payload is None:
        raise ValueError("canon extractor did not return a JSON object")
    return normalize_canon_candidate(payload)
