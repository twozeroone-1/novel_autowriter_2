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
