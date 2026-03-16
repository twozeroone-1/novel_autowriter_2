from copy import deepcopy


def _normalize_work_metadata(*, project_name: str, platform_config: dict) -> dict:
    return {
        "title": str(platform_config.get("work_title") or project_name),
        "description": str(platform_config.get("work_description", "")),
        "genre": str(platform_config.get("genre", "")),
        "age_grade": str(platform_config.get("default_age_grade", "general")),
        "cover_path": str(platform_config.get("cover_path", "")),
    }


def _resolve_episode_title(*, source_payload: dict, job: dict, target: dict) -> str:
    return str(
        target.get("episode_title")
        or job.get("chapter_title")
        or source_payload.get("title")
        or ""
    ).strip()


def _build_platform_package(*, project_name: str, platform_name: str, source_payload: dict, job: dict, target: dict, config: dict) -> dict:
    platform_config = deepcopy(config.get("platforms", {}).get(platform_name, {}))
    work_id = str(target.get("work_id") or platform_config.get("work_id") or "").strip()
    upload_request = {
        "episode_title": _resolve_episode_title(source_payload=source_payload, job=job, target=target),
        "content": str(source_payload.get("content", "")),
        "publish_mode": str(target.get("publish_mode", "immediate")),
        "visibility": str(target.get("visibility", "public")),
        "reserved_at": target.get("reserved_at"),
    }
    return {
        "work_id": work_id,
        "work_metadata": _normalize_work_metadata(project_name=project_name, platform_config=platform_config),
        "upload_request": upload_request,
        "expected_publication": deepcopy(upload_request),
    }


def build_publish_packages(*, project_name: str, source_payload: dict, job: dict, config: dict) -> dict:
    packages: dict[str, dict] = {}
    for platform_name, target in deepcopy(job.get("targets", {})).items():
        if not isinstance(target, dict) or not target.get("selected"):
            continue
        packages[str(platform_name)] = _build_platform_package(
            project_name=project_name,
            platform_name=str(platform_name),
            source_payload=source_payload,
            job=job,
            target=target,
            config=config,
        )

    return {
        "source": {
            "title": str(source_payload.get("title", "")),
            "episode_id": str(source_payload.get("episode_id", "")),
            "artifact_status": str(source_payload.get("artifact_status", "")),
        },
        "packages": packages,
    }
