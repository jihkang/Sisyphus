from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..episode_trace import EpisodeStep


class EpisodeTracePort(Protocol):
    def append(self, episode_step: EpisodeStep) -> Path: ...

    def next_step(self, episode_id: str) -> int: ...

    def read(self, *, episode_id: str | None = None) -> list[dict[str, object]]: ...


__all__ = ["EpisodeTracePort"]
