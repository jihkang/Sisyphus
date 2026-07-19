from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    relative_path: str
    digest: str | None = None


__all__ = ["ArtifactRef"]
