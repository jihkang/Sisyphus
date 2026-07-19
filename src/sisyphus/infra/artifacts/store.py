from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ...application.results.artifacts import ArtifactRef
from ...config import SisyphusConfig
from ...shared.paths import contained_path, task_dir as resolve_task_dir
from ..persistence.atomic_text import write_text_file
from ..persistence.json_store import write_json_file


class RepositoryArtifactStore:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._repo_root = repo_root
        self._config = config

    def write_json(
        self,
        task_id: str,
        relative_path: str,
        payload: Mapping[str, object],
    ) -> ArtifactRef:
        write_json_file(self._path(task_id, relative_path), dict(payload))
        return ArtifactRef(relative_path=relative_path)

    def write_text(self, task_id: str, relative_path: str, content: str) -> ArtifactRef:
        write_text_file(self._path(task_id, relative_path), content)
        return ArtifactRef(relative_path=relative_path)

    def resolve(self, task_id: str, relative_path: str) -> Path:
        return self._path(task_id, relative_path)

    def _path(self, task_id: str, relative_path: str) -> Path:
        directory = resolve_task_dir(self._repo_root, self._config.task_dir, task_id)
        return contained_path(directory, relative_path, require_relative=True)


__all__ = ["RepositoryArtifactStore"]
