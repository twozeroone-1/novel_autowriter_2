from pathlib import Path

from core.app_paths import DATA_PROJECTS_DIR
from core.episode_artifact_store import EpisodeArtifactStore


def load_chapter_source(project_name: str, source_path: str | Path, *, episode_id: str | None = None) -> dict[str, str | Path]:
    artifact_payload = _load_episode_artifact_source(project_name, episode_id)
    if artifact_payload is not None:
        return artifact_payload

    resolved_path = resolve_project_source_path(project_name, source_path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Chapter source does not exist: {resolved_path}")

    content = resolved_path.read_text(encoding="utf-8")
    return {
        "path": resolved_path,
        "title": _extract_title(content, resolved_path),
        "content": content,
        "episode_id": episode_id or "",
        "artifact_status": "legacy",
    }


def resolve_project_source_path(project_name: str, source_path: str | Path) -> Path:
    candidate = Path(source_path)
    if candidate.is_absolute():
        return candidate
    return (DATA_PROJECTS_DIR / project_name / candidate).resolve()


def _extract_title(content: str, resolved_path: Path) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if heading:
                return heading
    return resolved_path.stem


def _load_episode_artifact_source(project_name: str, episode_id: str | None) -> dict[str, str | Path] | None:
    if not episode_id:
        return None

    store = EpisodeArtifactStore(project_name=project_name)
    manifest = store.load_manifest()
    episode = manifest.get("episodes", {}).get(episode_id)
    if not isinstance(episode, dict):
        return None

    preferred_paths = (
        ("publishable", store.publishable_dir / f"{episode_id}.md"),
        ("published", store.published_dir / f"{episode_id}.md"),
        ("draft", store.drafts_dir / f"{episode_id}.md"),
    )
    for artifact_status, path in preferred_paths:
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        canon_update = store.load_canon_update(episode_id)
        return {
            "path": path,
            "title": _extract_title(content, path),
            "content": content,
            "episode_id": episode_id,
            "artifact_status": artifact_status,
            "canon_update": canon_update or {},
        }
    return None
