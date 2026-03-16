import json


def build_worldview_context(worldview: str, tone_and_manner: str) -> str:
    return f"""[STORY BIBLE] (세계관 및 기본 설정)
{worldview}

[STYLE GUIDE] (문체 및 작성 지침)
{tone_and_manner}
"""


def build_continuity_context(continuity: str) -> str:
    return f"""[CONTINUITY] (고정 설정, 절대 바뀌면 안 되는 규칙)
{continuity}
"""


def build_canon_context(canon_state: dict) -> str:
    return f"""[CANON FACTS] (발행 완료 회차 기준 확정 사실)
{json.dumps(canon_state, ensure_ascii=False, indent=2)}
"""


def build_release_policy_context(release_policy: dict) -> str:
    return f"""[RELEASE POLICY] (플랫폼별 발행 정책)
{json.dumps(release_policy, ensure_ascii=False, indent=2)}
"""


def build_state_context(state: str, summary_of_previous: str) -> str:
    return f"""[STATE] (현재 회차 상태, 갈등, 감정선)
{state}

[PREVIOUS_SUMMARY] (이전 줄거리 요약)
{summary_of_previous}
"""


def build_character_context(characters: list[dict]) -> str:
    if not characters:
        return "[등장인물 정보 없음]"

    lines = ["[주요 등장인물 프로필]"]
    for char in characters:
        traits = ", ".join(char.get("traits", []))
        lines.append(f"- {char['name']} ({char['role']}): {char['description']} (특징: {traits})")
    return "\n".join(lines)


def build_plot_block(*, plot_outline: str, include_plot: bool, plot_strength: str) -> str:
    if not include_plot or not plot_outline:
        return ""

    return f"""
[PLOT OUTLINE] (?κ린 ?뚮’ 媛?대뱶)
{plot_outline}

[?뚮’ 諛섏쁺 媛뺣룄]
{plot_strength}
"""


def build_generation_prompt(
    *,
    worldview_context: str,
    continuity_context: str,
    canon_context: str,
    release_policy_context: str,
    state_context: str,
    character_context: str,
    plot_block: str,
    user_instruction: str,
    length_goal: int,
) -> str:
    return f"""당신은 프로 웹소설 작가입니다. 다음 설정과 등장인물 정보를 바탕으로 다음 회차 본문을 작성해 주세요.
CONTINUITY를 깨지 말고, STATE의 갈등과 감정선을 자연스럽게 이어 주세요.

{worldview_context}
{continuity_context}
{canon_context}
{release_policy_context}
{state_context}
{character_context}
{plot_block}

[이번 회차 작성 지시사항]
{user_instruction}

[분량 및 서술 조건]
- 목표 분량: 공백 포함 약 {length_goal}자
- 제목은 생략하고 본문만 출력
"""
