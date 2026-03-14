import re


BLOCKED_MARKERS = ("TODO", "초안", "검수리포트")
MIN_CONTENT_LENGTH = 200
MAX_IDENTICAL_LINE_REPEAT = 4


def validate_origin_draft(*, title: str, content: str) -> dict:
    errors: list[str] = []
    normalized_title = str(title or "").strip()
    normalized_content = str(content or "").strip()

    if not re.search(r"\d+\s*화", normalized_title):
        errors.append("missing episode number in title")

    if len(normalized_content) < MIN_CONTENT_LENGTH:
        errors.append("content too short")

    for marker in BLOCKED_MARKERS:
        if marker in normalized_title or marker in normalized_content:
            errors.append(f"blocked marker detected: {marker}")

    if _has_repeated_lines(normalized_content):
        errors.append("repeated lines detected")

    if normalized_title.startswith("#") and not normalized_content:
        errors.append("empty heading body")

    return {
        "status": "failed" if errors else "passed",
        "errors": errors,
    }


def _has_repeated_lines(content: str) -> bool:
    previous = ""
    streak = 0
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == previous:
            streak += 1
        else:
            previous = line
            streak = 1
        if streak > MAX_IDENTICAL_LINE_REPEAT:
            return True
    return False
