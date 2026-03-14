import json
import os
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Optional

from core.generator import Generator
from core.model_catalog import get_model_pricing

FIELD_BUDGETS = {
    "worldview": {
        "label": "STORY_BIBLE",
        "recommended_max_chars": 1500,
        "tip": "배경, 핵심 규칙, 주인공 목표만 남기고 길면 `STORY_BIBLE 압축`을 쓰세요.",
    },
    "tone_and_manner": {
        "label": "STYLE_GUIDE",
        "recommended_max_chars": 600,
        "tip": "취향 설명보다 시점, 문장 길이, 금지 표현 같은 규칙만 남기는 편이 낫습니다.",
    },
    "continuity": {
        "label": "CONTINUITY",
        "recommended_max_chars": 900,
        "tip": "바뀌면 안 되는 사실만 적고, 해설 문장은 줄이는 쪽이 안전합니다.",
    },
    "state": {
        "label": "STATE",
        "recommended_max_chars": 500,
        "tip": "최근 갈등, 감정선, 다음 회차 목표만 남기고 오래된 설정은 빼세요.",
    },
    "summary_of_previous": {
        "label": "PREVIOUS_SUMMARY",
        "recommended_max_chars": 1200,
        "tip": "오래된 내용은 압축하고 최근 2~4화 중심으로 유지하는 편이 좋습니다.",
    },
}

DEFAULT_OUTPUT_TOKEN_RATIO = 0.62


def build_workspace_budget_snapshot(snapshot: Mapping[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key in FIELD_BUDGETS:
        value = snapshot.get(key, "")
        normalized[key] = "" if value is None else str(value)
    return normalized


def _get_primary_api_key() -> str:
    api_key_env = os.getenv("GOOGLE_API_KEY", "")
    keys = [key.strip() for key in api_key_env.split(",") if key.strip()]
    if not keys:
        raise RuntimeError("GOOGLE_API_KEY가 설정되지 않았습니다.")
    return keys[0]


def count_text_tokens(text: str, model_name: str) -> int:
    api_key = _get_primary_api_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:countTokens?key={api_key}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": text}],
            }
        ]
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return int(data.get("totalTokens", 0))


def get_field_stats(config: dict) -> list[dict]:
    budget_snapshot = build_workspace_budget_snapshot(config)
    rows = []
    for key, meta in FIELD_BUDGETS.items():
        chars = len(budget_snapshot[key])
        recommended = meta["recommended_max_chars"]
        if chars == 0:
            status = "비어 있음"
        elif chars <= recommended:
            status = "적정"
        elif chars <= int(recommended * 1.5):
            status = "주의"
        else:
            status = "과다"
        rows.append(
            {
                "key": key,
                "label": meta["label"],
                "chars": chars,
                "recommended_max_chars": recommended,
                "status": status,
                "tip": meta["tip"],
            }
        )
    return rows


def get_budget_recommendations(config: dict) -> list[str]:
    recommendations: list[str] = []
    stats = {row["key"]: row for row in get_field_stats(build_workspace_budget_snapshot(config))}

    if stats["state"]["chars"] == 0:
        recommendations.append("STATE가 비어 있으면 최근 갈등과 감정선 연결이 약해질 수 있습니다. 짧게라도 현재 상태를 적어두는 편이 좋습니다.")

    if stats["worldview"]["chars"] > FIELD_BUDGETS["worldview"]["recommended_max_chars"]:
        recommendations.append("STORY_BIBLE은 배경, 핵심 규칙, 주인공 목표만 남기고 나머지는 압축하는 편이 안정적입니다.")
    if stats["tone_and_manner"]["chars"] > FIELD_BUDGETS["tone_and_manner"]["recommended_max_chars"]:
        recommendations.append("STYLE_GUIDE는 취향 설명보다 시점, 문장 길이, 금지 표현 같은 규칙형 문장으로 줄이는 편이 좋습니다.")
    if stats["continuity"]["chars"] > FIELD_BUDGETS["continuity"]["recommended_max_chars"]:
        recommendations.append("CONTINUITY는 절대 바뀌면 안 되는 사실만 남기고, 설명 문장은 줄이는 편이 안전합니다.")
    if stats["state"]["chars"] > FIELD_BUDGETS["state"]["recommended_max_chars"]:
        recommendations.append("STATE는 최근 갈등, 감정선, 다음 목표만 유지하고 오래된 사건은 summary로 넘기는 편이 좋습니다.")
    if stats["summary_of_previous"]["chars"] > FIELD_BUDGETS["summary_of_previous"]["recommended_max_chars"]:
        recommendations.append("PREVIOUS_SUMMARY는 오래된 내용보다 최근 2~4화 중심으로 유지하고, 누적분은 압축하세요.")

    total_core_chars = sum(
        stats[key]["chars"] for key in ("worldview", "tone_and_manner", "continuity", "state", "summary_of_previous")
    )
    if total_core_chars > 5000:
        recommendations.append("핵심 설정 5개 합계가 5,000자를 넘으면 문맥 노이즈가 늘 수 있습니다. 4,000~5,000자 안쪽이 다루기 쉽습니다.")

    if not recommendations:
        recommendations.append("현재 설정 길이는 무난합니다. 길이를 더 늘리기보다 중복 설명을 줄이고 STATE를 최신 상태로 유지하세요.")

    return recommendations


def find_latest_sample_chapter(chapters_dir: Path) -> Optional[Path]:
    if not chapters_dir.exists():
        return None

    candidates = []
    for path in chapters_dir.glob("*.md"):
        name = path.name
        if "검수리포트" in name or "_수정본" in name or "_초안" in name:
            continue
        candidates.append(path)

    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def estimate_generation_cost_report(
    generator: Generator,
    instruction: str,
    target_length: int,
    include_plot: bool = False,
    plot_strength: str = "balanced",
    model_name: str = "gemini-2.5-flash",
) -> dict:
    prompt = generator.ctx.build_generation_prompt(
        instruction,
        target_length,
        include_plot=include_plot,
        plot_strength=plot_strength,
    )
    system_instruction = (
        f"너는 사용자가 제시한 목표 분량(공백 포함 약 {target_length}자 내외)을 엄격하게 지키면서 기승전결이 있는 회차를 작성하는 프로 소설가다."
    )

    prompt_tokens = count_text_tokens(prompt, model_name)
    system_tokens = count_text_tokens(system_instruction, model_name)
    input_tokens = prompt_tokens + system_tokens

    sample_path = find_latest_sample_chapter(generator.chapters_dir)
    sample_ratio = DEFAULT_OUTPUT_TOKEN_RATIO
    output_ratio_source = "기본 추정치"
    sample_chars = 0
    sample_tokens = 0
    if sample_path:
        sample_text = sample_path.read_text(encoding="utf-8")
        sample_chars = len(sample_text)
        if sample_chars > 0:
            try:
                sample_tokens = count_text_tokens(sample_text, model_name)
            except Exception:
                sample_tokens = 0
            if sample_tokens > 0:
                sample_ratio = sample_tokens / sample_chars
                output_ratio_source = f"최근 저장 회차 기준: {sample_path.name}"

    estimated_output_tokens = max(1, round(target_length * sample_ratio))
    pricing = get_model_pricing(model_name)

    input_cost_usd = None
    output_cost_usd = None
    total_cost_usd = None
    if pricing:
        input_cost_usd = (input_tokens / 1_000_000) * pricing["input"]
        output_cost_usd = (estimated_output_tokens / 1_000_000) * pricing["output"]
        total_cost_usd = input_cost_usd + output_cost_usd

    return {
        "model_name": model_name,
        "instruction_chars": len(instruction),
        "target_length": target_length,
        "include_plot": include_plot,
        "plot_strength": plot_strength,
        "prompt_chars": len(prompt),
        "prompt_tokens": prompt_tokens,
        "system_tokens": system_tokens,
        "input_tokens": input_tokens,
        "estimated_output_tokens": estimated_output_tokens,
        "sample_chars": sample_chars,
        "sample_tokens": sample_tokens,
        "output_ratio_source": output_ratio_source,
        "output_tokens_per_char": sample_ratio,
        "pricing": pricing,
        "input_cost_usd": input_cost_usd,
        "output_cost_usd": output_cost_usd,
        "total_cost_usd": total_cost_usd,
    }
