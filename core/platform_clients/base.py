from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformWorkMetadata:
    title: str
    description: str = ""
    genre: str = ""
    age_grade: str = "general"
    cover_path: str = ""


@dataclass(frozen=True)
class EpisodeUploadRequest:
    work_id: str
    episode_title: str
    content: str
    publish_mode: str = "immediate"
    visibility: str = "public"
    reserved_at: str | None = None


@dataclass(frozen=True)
class PlatformActionResult:
    status: str
    success: bool
    work_id: str = ""
    episode_id: str = ""
    error_type: str = ""
    error_text: str = ""


class PlatformError(RuntimeError):
    def __init__(self, message: str, *, error_type: str):
        super().__init__(message)
        self.error_type = error_type


class BasePlatformClient(ABC):
    SUPPORTED_PUBLISH_MODES = ("immediate",)

    @classmethod
    def supported_publish_modes(cls) -> tuple[str, ...]:
        raw_modes = getattr(cls, "SUPPORTED_PUBLISH_MODES", ("immediate",))
        normalized = []
        for mode in raw_modes:
            text = str(mode).strip().lower()
            if text and text not in normalized:
                normalized.append(text)
        return tuple(normalized) or ("immediate",)

    @abstractmethod
    def login(self) -> PlatformActionResult:
        raise NotImplementedError

    @abstractmethod
    def ensure_work(self, metadata: PlatformWorkMetadata, work_id: str = "") -> PlatformActionResult:
        raise NotImplementedError

    @abstractmethod
    def upload_episode(self, request: EpisodeUploadRequest) -> PlatformActionResult:
        raise NotImplementedError

    @abstractmethod
    def set_publish_options(self, payload: dict) -> PlatformActionResult:
        raise NotImplementedError

    @abstractmethod
    def verify_publication(self, expected: dict) -> PlatformActionResult:
        raise NotImplementedError

    @abstractmethod
    def smoke_check_editor(self, work_id: str) -> PlatformActionResult:
        raise NotImplementedError


def supported_publish_modes(client_class: type[BasePlatformClient]) -> tuple[str, ...]:
    return client_class.supported_publish_modes()


def supports_publish_mode(client_class: type[BasePlatformClient], publish_mode: str) -> bool:
    normalized_mode = str(publish_mode or "immediate").strip().lower()
    return normalized_mode in supported_publish_modes(client_class)
