from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecordExternalReviewCommand:
    task_id: str
    envelope_path: str


__all__ = ["RecordExternalReviewCommand"]
