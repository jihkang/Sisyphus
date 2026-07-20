from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ExternalReviewEvidenceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExternalReviewEvidence:
    relative_path: str
    digest: str
    size_bytes: int
    current_head_sha: str
    dirty_paths: tuple[str, ...]


class ExternalReviewEvidencePort(Protocol):
    def inspect(self, workspace: str, relative_path: str) -> ExternalReviewEvidence: ...


__all__ = [
    "ExternalReviewEvidence",
    "ExternalReviewEvidenceError",
    "ExternalReviewEvidencePort",
]
