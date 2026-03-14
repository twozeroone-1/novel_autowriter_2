import json
import re
from copy import deepcopy
from pathlib import Path

from core.app_paths import DATA_PROJECTS_DIR
from core.file_utils import atomic_write_json, atomic_write_text


DEFAULT_MANIFEST = {
    "episodes": {},
}


class EpisodeArtifactStore:
    def __init__(self, project_name: str):
        self.project_name = project_name

    @property
    def episodes_dir(self) -> Path:
        return DATA_PROJECTS_DIR / self.project_name / "episodes"

    @property
    def manifest_path(self) -> Path:
        return self.episodes_dir / "manifests.json"

    @property
    def drafts_dir(self) -> Path:
        return self.episodes_dir / "drafts"

    @property
    def publishable_dir(self) -> Path:
        return self.episodes_dir / "publishable"

    @property
    def published_dir(self) -> Path:
        return self.episodes_dir / "published"

    def load_manifest(self) -> dict:
        if not self.manifest_path.exists():
            return deepcopy(DEFAULT_MANIFEST)
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return deepcopy(DEFAULT_MANIFEST)
        episodes = payload.get("episodes", {}) if isinstance(payload, dict) else {}
        return {"episodes": deepcopy(episodes) if isinstance(episodes, dict) else {}}

    def save_manifest(self, manifest: dict) -> None:
        atomic_write_json(self.manifest_path, manifest)

    def create_draft(self, *, title: str, content: str, episode_id: str | None = None) -> dict:
        manifest = self.load_manifest()
        episodes = manifest.setdefault("episodes", {})

        if episode_id and episode_id in episodes:
            sequence = int(episodes[episode_id]["sequence"])
        else:
            sequence = _extract_episode_sequence(title) or self._next_sequence(episodes)
            episode_id = f"ep_{sequence:03d}"

        draft_path = self.drafts_dir / f"{episode_id}.md"
        atomic_write_text(draft_path, content)
        episodes[episode_id] = {
            "episode_id": episode_id,
            "sequence": sequence,
            "title": title,
            "status": "draft",
            "draft_path": str(draft_path.relative_to(DATA_PROJECTS_DIR / self.project_name)),
            "publishable_path": str((self.publishable_dir / f"{episode_id}.md").relative_to(DATA_PROJECTS_DIR / self.project_name)),
            "published_path": str((self.published_dir / f"{episode_id}.md").relative_to(DATA_PROJECTS_DIR / self.project_name)),
        }
        self.save_manifest(manifest)
        return deepcopy(episodes[episode_id])

    def promote_to_publishable(self, episode_id: str) -> dict:
        manifest = self.load_manifest()
        episode = deepcopy(manifest.get("episodes", {}).get(episode_id, {}))
        if not episode:
            raise KeyError(f"Unknown episode_id: {episode_id}")

        source = self.drafts_dir / f"{episode_id}.md"
        target = self.publishable_dir / f"{episode_id}.md"
        atomic_write_text(target, source.read_text(encoding="utf-8"))
        manifest["episodes"][episode_id]["status"] = "publishable"
        self.save_manifest(manifest)
        episode = deepcopy(manifest["episodes"][episode_id])
        return episode

    def mark_published(self, episode_id: str) -> dict:
        manifest = self.load_manifest()
        episode = deepcopy(manifest.get("episodes", {}).get(episode_id, {}))
        if not episode:
            raise KeyError(f"Unknown episode_id: {episode_id}")

        source = self.publishable_dir / f"{episode_id}.md"
        if not source.exists():
            source = self.drafts_dir / f"{episode_id}.md"
        target = self.published_dir / f"{episode_id}.md"
        atomic_write_text(target, source.read_text(encoding="utf-8"))
        manifest["episodes"][episode_id]["status"] = "published"
        self.save_manifest(manifest)
        return deepcopy(manifest["episodes"][episode_id])

    def _next_sequence(self, episodes: dict) -> int:
        sequences = [int(payload.get("sequence", 0)) for payload in episodes.values() if isinstance(payload, dict)]
        return max(sequences, default=0) + 1


def _extract_episode_sequence(title: str) -> int | None:
    match = re.search(r"(\d+)\s*화", title)
    if not match:
        return None
    return int(match.group(1))
