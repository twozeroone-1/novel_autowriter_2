from core.origin_quality import validate_origin_draft


RECOVERABLE_ERRORS = {
    "repeated lines detected",
}


def evaluate_publish_source(source_payload: dict) -> dict:
    title = str(source_payload.get("title", ""))
    content = str(source_payload.get("content", ""))
    raw_report = validate_origin_draft(title=title, content=content)
    errors = [str(item) for item in raw_report.get("errors", [])]
    recoverable_errors = [item for item in errors if item in RECOVERABLE_ERRORS]
    hard_fail_errors = [item for item in errors if item not in RECOVERABLE_ERRORS]

    if not errors:
        status = "publishable"
    elif hard_fail_errors:
        status = "hard_fail"
    elif recoverable_errors:
        status = "retry_possible"
    else:
        status = "hard_fail"

    return {
        "status": status,
        "errors": errors,
        "signals": {
            "title_present": bool(title.strip()),
            "content_length": len(content.strip()),
        },
        "raw_report": raw_report,
    }
