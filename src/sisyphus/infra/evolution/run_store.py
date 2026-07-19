from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path

from ...application.evolution_runs import (
    validate_evolution_artifact_name,
    validate_evolution_run_id,
)
from ...shared.paths import contained_path
from ..persistence.atomic_text import fsync_directory


DEFAULT_EVOLUTION_ARTIFACT_READ_LIMIT = 8 * 1024 * 1024


class RepositoryEvolutionRunStore:
    def __init__(self, repo_root: Path, *, read_limit: int = DEFAULT_EVOLUTION_ARTIFACT_READ_LIMIT) -> None:
        if read_limit < 1:
            raise ValueError("evolution artifact read limit must be positive")
        self._repo_root = repo_root.resolve()
        self._runs_root = contained_path(
            self._repo_root,
            Path(".planning") / "evolution" / "runs",
            require_relative=True,
        )
        self._read_limit = read_limit

    def create_run(self, run_id: str) -> Path:
        run_dir = self.artifact_dir(run_id)
        parent_created = not self._runs_root.exists()
        self._runs_root.mkdir(parents=True, exist_ok=True)
        if parent_created:
            fsync_directory(self._runs_root.parent)
        run_dir.mkdir(exist_ok=False)
        fsync_directory(self._runs_root)
        return run_dir

    def artifact_dir(self, run_id: str) -> Path:
        return contained_path(
            self._runs_root,
            validate_evolution_run_id(run_id),
            require_relative=True,
        )

    def run_exists(self, run_id: str) -> bool:
        return self.artifact_dir(run_id).is_dir()

    def artifact_exists(self, run_id: str, name: str) -> bool:
        return self._artifact_path(run_id, name).is_file()

    def append_json(self, run_id: str, name: str, payload: Mapping[str, object]) -> Path:
        rendered = json.dumps(dict(payload), indent=2) + "\n"
        return self.append_text(run_id, name, rendered)

    def append_text(self, run_id: str, name: str, content: str) -> Path:
        path = self._artifact_path(run_id, name)
        descriptor = os.open(
            path,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o644,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            raise
        fsync_directory(path.parent)
        return path

    def read_json(self, run_id: str, name: str) -> Mapping[str, object] | None:
        text = self.read_text(run_id, name)
        if text is None:
            return None
        payload = json.loads(text)
        if not isinstance(payload, Mapping):
            raise ValueError(f"evolution run artifact must be an object: {name}")
        return {str(key): value for key, value in payload.items()}

    def read_text(self, run_id: str, name: str) -> str | None:
        path = self._artifact_path(run_id, name)
        try:
            descriptor = os.open(
                path,
                os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
            )
        except FileNotFoundError:
            return None
        with os.fdopen(descriptor, "rb") as handle:
            content = handle.read(self._read_limit + 1)
        if len(content) > self._read_limit:
            raise ValueError(f"evolution run artifact exceeds read limit: {name}")
        return content.decode("utf-8")

    def _artifact_path(self, run_id: str, name: str) -> Path:
        run_dir = self.artifact_dir(run_id)
        return contained_path(
            run_dir,
            validate_evolution_artifact_name(name),
            require_relative=True,
        )


__all__ = ["DEFAULT_EVOLUTION_ARTIFACT_READ_LIMIT", "RepositoryEvolutionRunStore"]
