def summarize_publish_attempt(*, job: dict, platform_results: dict) -> dict:
    selected_statuses = [
        payload.get("status", "pending")
        for payload in job.get("targets", {}).values()
        if isinstance(payload, dict) and payload.get("selected")
    ]

    needs_user_action = any(
        isinstance(payload, dict) and payload.get("error_type") == "requires_user_action"
        for payload in platform_results.values()
    )
    last_error = next(
        (
            str(payload.get("error_text", "")).strip()
            for payload in platform_results.values()
            if isinstance(payload, dict) and str(payload.get("error_text", "")).strip()
        ),
        "",
    )

    if not selected_statuses:
        return {
            "job_status": "failed",
            "runtime_status": "blocked",
            "incident_type": "data_integrity_incident",
            "needs_user_action": False,
            "last_error": last_error,
        }

    if all(status == "done" for status in selected_statuses):
        return {
            "job_status": "done",
            "runtime_status": "idle",
            "incident_type": "",
            "needs_user_action": False,
            "last_error": "",
        }

    if needs_user_action:
        return {
            "job_status": "failed",
            "runtime_status": "paused",
            "incident_type": "credential_incident",
            "needs_user_action": True,
            "last_error": last_error,
        }

    if any(status == "done" for status in selected_statuses):
        return {
            "job_status": "partial_failed",
            "runtime_status": "cooldown",
            "incident_type": "platform_incident",
            "needs_user_action": False,
            "last_error": last_error,
        }

    return {
        "job_status": "failed",
        "runtime_status": "cooldown",
        "incident_type": "platform_incident",
        "needs_user_action": False,
        "last_error": last_error,
    }
