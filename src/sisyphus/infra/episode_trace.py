from __future__ import annotations

import json
import os
from pathlib import Path

from ..application.episode_trace import EpisodeStep, validate_episode_id
from ..shared.paths import contained_path
from .events import append_jsonl_text
from .persistence.file_lock import file_handle_lock


DEFAULT_EPISODE_DIR = Path("artifacts") / "episodes"
_READ_FLAGS = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)


class RepositoryEpisodeTraceStore:
    def __init__(self, task_dir: Path) -> None:
        self._task_dir = task_dir

    def append(self, episode_step: EpisodeStep) -> Path:
        path = self._episode_path(episode_step.episode_id)
        line = json.dumps(episode_step.to_dict(), separators=(",", ":"), sort_keys=True)
        append_jsonl_text(path, line)
        return path

    def next_step(self, episode_id: str) -> int:
        max_step = 0
        for payload in self.read(episode_id=episode_id):
            step = payload.get("step")
            if isinstance(step, int):
                max_step = max(max_step, step)
        return max_step + 1

    def read(self, *, episode_id: str | None = None) -> list[dict[str, object]]:
        normalized_episode_id = (
            validate_episode_id(episode_id) if episode_id is not None else None
        )
        episode_dir = contained_path(
            self._task_dir,
            DEFAULT_EPISODE_DIR,
            require_relative=True,
        )
        if not episode_dir.exists():
            return []
        paths = (
            [self._episode_path(normalized_episode_id)]
            if normalized_episode_id is not None
            else sorted(episode_dir.glob("*.jsonl"))
        )
        steps: list[dict[str, object]] = []
        for path in paths:
            contained_path(self._task_dir, path)
            if not path.exists():
                continue
            descriptor = os.open(path, _READ_FLAGS)
            with os.fdopen(descriptor, "r", encoding="utf-8") as handle, file_handle_lock(handle):
                lines = handle.read().splitlines()
            for line_number, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    steps.append(
                        {
                            "episode_id": path.stem,
                            "line": line_number,
                            "valid": False,
                            "error": f"invalid json: {exc.msg}",
                        }
                    )
                    continue
                if isinstance(payload, dict):
                    payload.setdefault("episode_id", path.stem)
                    payload.setdefault("line", line_number)
                    steps.append(payload)
        return steps

    def _episode_path(self, episode_id: str) -> Path:
        normalized = validate_episode_id(episode_id)
        return contained_path(
            self._task_dir,
            DEFAULT_EPISODE_DIR / f"{normalized}.jsonl",
            require_relative=True,
        )


__all__ = ["DEFAULT_EPISODE_DIR", "RepositoryEpisodeTraceStore"]
