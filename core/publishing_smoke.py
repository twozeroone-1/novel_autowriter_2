from copy import deepcopy

from core.platform_clients.base import PlatformError
from core.platform_clients.munpia import MunpiaClient
from core.platform_clients.novelpia import NovelpiaClient
from core.platform_credentials import load_platform_credentials
from core.publishing_readiness import build_publishing_readiness_snapshot
from core.publishing_store import PublishingStore


PLATFORM_CLIENTS = {
    "munpia": MunpiaClient,
    "novelpia": NovelpiaClient,
}


def run_publishing_smoke(
    *,
    project_name: str,
    platforms: list[str] | None = None,
    headless: bool | None = None,
    config: dict | None = None,
    credential_loader=load_platform_credentials,
    client_factory=None,
) -> dict:
    resolved_config = deepcopy(config) if isinstance(config, dict) else PublishingStore(project_name).load_config()
    selected_platforms = _resolve_selected_platforms(config=resolved_config, platforms=platforms)
    effective_headless = bool(resolved_config.get("browser", {}).get("headless", True)) if headless is None else bool(headless)
    build_client = client_factory or _default_client_factory
    readiness_snapshot = build_publishing_readiness_snapshot(
        project_name=project_name,
        config=resolved_config,
        credential_loader=credential_loader,
    )
    readiness_rows = {
        row["platform_name"]: row
        for row in readiness_snapshot.get("platform_rows", ())
        if isinstance(row, dict) and row.get("platform_name")
    }

    platform_results: dict[str, dict] = {}
    overall_success = True

    for platform_name in selected_platforms:
        platform_config = deepcopy(resolved_config.get("platforms", {}).get(platform_name, {}))
        row = readiness_rows.get(platform_name, {})
        readiness_failure = _build_readiness_failure(platform_name=platform_name, row=row)
        if readiness_failure is not None:
            platform_results[platform_name] = readiness_failure
            overall_success = False
            continue

        platform_config.setdefault("name", platform_name)
        client = build_client(
            platform_name=platform_name,
            username=credential_loader(project_name, platform_name)["username"],
            password=credential_loader(project_name, platform_name)["password"],
            platform_config=platform_config,
            headless=effective_headless,
        )
        try:
            work_id = str(platform_config.get("work_id", "")).strip()
            client.login()
            smoke_result = client.smoke_check_editor(work_id)
            platform_results[platform_name] = {
                "status": smoke_result.status,
                "success": smoke_result.success,
                "error_type": smoke_result.error_type,
                "error_text": smoke_result.error_text,
                "work_id": smoke_result.work_id or work_id,
            }
            overall_success = overall_success and bool(smoke_result.success)
        except PlatformError as exc:
            platform_results[platform_name] = _failure_result(
                error_type=exc.error_type,
                error_text=str(exc),
                work_id=work_id,
            )
            overall_success = False
        finally:
            if hasattr(client, "close"):
                client.close()

    return {
        "project_name": project_name,
        "checked_platforms": selected_platforms,
        "success": bool(selected_platforms) and overall_success,
        "platform_results": platform_results,
    }


def _resolve_selected_platforms(*, config: dict, platforms: list[str] | None) -> list[str]:
    if platforms:
        normalized = []
        for platform_name in platforms:
            text = str(platform_name).strip().lower()
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    resolved = []
    for platform_name, payload in config.get("platforms", {}).items():
        if not isinstance(payload, dict):
            continue
        if payload.get("enabled", False):
            resolved.append(str(platform_name).strip().lower())
    return resolved


def _failure_result(*, error_type: str, error_text: str, work_id: str = "") -> dict:
    return {
        "status": "failed",
        "success": False,
        "error_type": error_type,
        "error_text": error_text,
        "work_id": work_id,
    }


def _build_readiness_failure(*, platform_name: str, row: dict) -> dict | None:
    if not row.get("enabled", False):
        return _failure_result(
            error_type="requires_user_action",
            error_text=f"{platform_name} platform is disabled.",
        )
    if not row.get("has_credentials", False):
        return _failure_result(
            error_type="requires_user_action",
            error_text=f"{platform_name} credentials are missing.",
        )
    if not row.get("has_work_id", False):
        return _failure_result(
            error_type="requires_user_action",
            error_text=f"{platform_name} work_id is missing.",
        )
    if not row.get("has_upload_url_template", False):
        return _failure_result(
            error_type="requires_user_action",
            error_text=f"{platform_name} upload_url_template is missing.",
        )
    return None


def _default_client_factory(**kwargs):
    platform_name = kwargs.pop("platform_name")
    if platform_name == "munpia":
        return MunpiaClient(**kwargs)
    if platform_name == "novelpia":
        return NovelpiaClient(**kwargs)
    raise ValueError(f"Unsupported platform: {platform_name}")
