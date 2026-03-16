from core.origin_quality import validate_origin_draft


def evaluate_publish_source(source_payload: dict) -> dict:
    title = str(source_payload.get("title", ""))
    content = str(source_payload.get("content", ""))
    raw_report = validate_origin_draft(title=title, content=content)
    errors = [str(item) for item in raw_report.get("errors", [])]

    return {
        "status": "publishable" if raw_report.get("status") == "passed" else "hard_fail",
        "errors": errors,
        "signals": {
            "title_present": bool(title.strip()),
            "content_length": len(content.strip()),
        },
        "raw_report": raw_report,
    }
