from copy import deepcopy

from core.chapter_source import load_chapter_source
from core.platform_clients.base import EpisodeUploadRequest, PlatformError, PlatformWorkMetadata
from core.platform_clients.munpia import MunpiaClient
from core.platform_clients.novelpia import NovelpiaClient
from core.platform_credentials import load_platform_credentials


class PublishingExecutor:
    def __init__(
        self,
        *,
        project_name: str,
        credential_loader=load_platform_credentials,
        client_factory=None,
    ):
        self.project_name = project_name
        self.credential_loader = credential_loader
        self.client_factory = client_factory or self._default_client_factory

    def publish_job(self, *, job: dict, config: dict) -> dict:
        source_payload = load_chapter_source(
            self.project_name,
            job.get("source_path", ""),
            episode_id=str(job.get("episode_id", "")).strip() or None,
        )
        source_payload = _apply_source_override(source_payload=source_payload, source_override=job.get("source_override"))
        platform_results: dict[str, dict] = {}
        platform_config_updates: dict[str, dict] = {}

        for platform_name, target in deepcopy(job.get("targets", {})).items():
            if not isinstance(target, dict) or not target.get("selected"):
                continue

            platform_config = deepcopy(config.get("platforms", {}).get(platform_name, {}))
            if not platform_config.get("enabled", False):
                platform_results[platform_name] = {
                    "status": "failed",
                    "success": False,
                    "error_type": "permanent",
                    "error_text": f"{platform_name} platform is disabled.",
                }
                continue

            credentials = self.credential_loader(self.project_name, platform_name)
            if not credentials.get("username", "").strip() or not credentials.get("password", "").strip():
                platform_results[platform_name] = {
                    "status": "failed",
                    "success": False,
                    "error_type": "requires_user_action",
                    "error_text": f"{platform_name} credentials are missing.",
                }
                continue

            client = self.client_factory(
                platform_name=platform_name,
                username=credentials["username"],
                password=credentials["password"],
                platform_config=platform_config,
                headless=bool(config.get("browser", {}).get("headless", True)),
            )
            try:
                client.login()
                work_id = str(target.get("work_id", "")).strip() or str(platform_config.get("work_id", "")).strip()
                if not work_id:
                    metadata = PlatformWorkMetadata(
                        title=str(platform_config.get("work_title", self.project_name)),
                        description=str(platform_config.get("work_description", "")),
                        genre=str(platform_config.get("genre", "")),
                        age_grade=str(platform_config.get("default_age_grade", "general")),
                        cover_path=str(platform_config.get("cover_path", "")),
                    )
                    work_result = client.ensure_work(metadata, work_id="")
                    work_id = work_result.work_id
                    if work_id:
                        platform_config_updates[platform_name] = {"work_id": work_id}
                upload_result = client.upload_episode(
                    EpisodeUploadRequest(
                        work_id=work_id,
                        episode_title=str(target.get("episode_title") or job.get("chapter_title") or source_payload["title"]),
                        content=str(source_payload["content"]),
                        publish_mode=str(target.get("publish_mode", "immediate")),
                        visibility=str(target.get("visibility", "public")),
                        reserved_at=target.get("reserved_at"),
                    )
                )
                platform_results[platform_name] = {
                    "status": upload_result.status,
                    "success": upload_result.success,
                    "work_id": upload_result.work_id or work_id,
                    "episode_id": upload_result.episode_id,
                    "error_type": upload_result.error_type,
                    "error_text": upload_result.error_text,
                }
            except PlatformError as exc:
                platform_results[platform_name] = {
                    "status": "failed",
                    "success": False,
                    "error_type": exc.error_type,
                    "error_text": str(exc),
                }
            finally:
                if hasattr(client, "close"):
                    client.close()

        return {
            "source": source_payload,
            "platform_results": platform_results,
            "platform_config_updates": platform_config_updates,
        }

    def _default_client_factory(self, **kwargs):
        platform_name = kwargs.pop("platform_name")
        if platform_name == "munpia":
            return MunpiaClient(**kwargs)
        if platform_name == "novelpia":
            return NovelpiaClient(**kwargs)
        raise ValueError(f"Unsupported platform: {platform_name}")


def _apply_source_override(*, source_payload: dict, source_override: dict | None) -> dict:
    if not isinstance(source_override, dict):
        return source_payload

    merged = deepcopy(source_payload)
    for field in ("title", "content"):
        value = source_override.get(field)
        if isinstance(value, str) and value.strip():
            merged[field] = value
    return merged
