import re


STRUCTURE_AUXILIARY_MARKERS = ("초안", "수정본", "검수리포트")
MAX_IDENTICAL_LINE_REPEAT = 4
MIN_CHAPTER_SHAPED_CONTENT_LENGTH = 80


def _extract_heading_title(content: str) -> str:
    for raw_line in str(content or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            return line.lstrip("#").strip()
        break
    return ""


def _extract_episode_number(text: str) -> int | None:
    match = re.search(r"(\d+)\s*화", str(text or ""))
    if not match:
        return None
    return int(match.group(1))


def _has_auxiliary_marker(text: str) -> bool:
    normalized = str(text or "")
    return any(marker in normalized for marker in STRUCTURE_AUXILIARY_MARKERS)


def _detect_repeated_lines(content: str) -> int:
    previous = ""
    streak = 0
    repeated_line_count = 0
    for raw_line in str(content or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == previous:
            streak += 1
        else:
            previous = line
            streak = 1
        if streak > MAX_IDENTICAL_LINE_REPEAT:
            repeated_line_count += 1
    return repeated_line_count


def evaluate_publish_structure(source_payload: dict) -> dict:
    title = str(source_payload.get("title", "")).strip()
    content = str(source_payload.get("content", "")).strip()
    heading_title = _extract_heading_title(content)
    title_episode_number = _extract_episode_number(title)
    heading_episode_number = _extract_episode_number(heading_title)
    repeated_line_count = _detect_repeated_lines(content)

    signals = {
        "heading_present": bool(heading_title),
        "title_episode_number": title_episode_number,
        "heading_episode_number": heading_episode_number,
        "repeated_line_count": repeated_line_count,
    }
    errors: list[str] = []

    if len(content) < MIN_CHAPTER_SHAPED_CONTENT_LENGTH:
        errors.append("content is not chapter shaped")
        return {"status": "hard_fail", "errors": errors, "signals": signals}

    if title_episode_number is not None and heading_episode_number is not None:
        if title_episode_number != heading_episode_number:
            errors.append("episode number mismatch between title and heading")
            return {"status": "hard_fail", "errors": errors, "signals": signals}

    if not heading_title:
        errors.append("missing chapter heading")

    if _has_auxiliary_marker(content) or _has_auxiliary_marker(title):
        errors.append("auxiliary marker detected")

    if repeated_line_count > 0:
        errors.append("repeated line spam detected")

    if errors:
        return {"status": "retry_possible", "errors": errors, "signals": signals}

    return {"status": "passed", "errors": [], "signals": signals}
