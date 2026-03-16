from __future__ import annotations

from core.platform_credentials import load_platform_credentials


PLATFORM_LABELS = {
    "munpia": "문피아",
    "novelpia": "노벨피아",
}


def build_publishing_readiness_snapshot(
    *,
    project_name: str,
    config: dict,
    credential_loader=load_platform_credentials,
    config_exists: bool = True,
) -> dict:
    platform_rows: list[dict] = []
    blockers: list[str] = []
    recommended_actions: list[str] = []
    enabled_platform_count = 0
    ready_platform_count = 0

    for platform_name, platform_label in PLATFORM_LABELS.items():
        platform_config = config.get("platforms", {}).get(platform_name, {})
        enabled = bool(platform_config.get("enabled", False))
        has_credentials = False
        has_work_id = bool(str(platform_config.get("work_id", "")).strip())
        has_upload_url_template = bool(str(platform_config.get("upload_url_template", "")).strip())

        if enabled:
            enabled_platform_count += 1
            credentials = credential_loader(project_name, platform_name)
            has_credentials = bool(
                str(credentials.get("username", "")).strip() and str(credentials.get("password", "")).strip()
            )
            if not has_credentials:
                blockers.append(f"{platform_label} 계정이 설정되지 않았습니다.")
                recommended_actions.append("플랫폼 계정을 keyring 또는 env fallback으로 설정하세요.")
            if not has_work_id:
                blockers.append(f"{platform_label} work_id가 비어 있습니다.")
                recommended_actions.append("플랫폼 작품 매핑(work_id / 업로드 URL)을 채우세요.")
            if not has_upload_url_template:
                blockers.append(f"{platform_label} 업로드 URL이 비어 있습니다.")
                recommended_actions.append("플랫폼 작품 매핑(work_id / 업로드 URL)을 채우세요.")
            if has_credentials and has_work_id and has_upload_url_template:
                ready_platform_count += 1

        platform_rows.append(
            {
                "platform_name": platform_name,
                "platform_label": platform_label,
                "enabled": enabled,
                "has_credentials": has_credentials,
                "has_work_id": has_work_id,
                "has_upload_url_template": has_upload_url_template,
                "ready": enabled and has_credentials and has_work_id and has_upload_url_template,
            }
        )

    if enabled_platform_count == 0:
        blockers.append("활성화된 업로드 플랫폼이 없습니다.")
        recommended_actions.append("외부 플랫폼 업로드에서 업로드 플랫폼을 활성화하세요.")

    return {
        "config_exists": config_exists,
        "platform_rows": tuple(platform_rows),
        "enabled_platform_count": enabled_platform_count,
        "ready_platform_count": ready_platform_count,
        "publishing_ready": enabled_platform_count > 0 and ready_platform_count == enabled_platform_count,
        "blockers": tuple(_dedupe_preserving_order(blockers)),
        "recommended_actions": tuple(_dedupe_preserving_order(recommended_actions)),
    }


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped
