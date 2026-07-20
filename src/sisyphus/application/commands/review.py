from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecordExternalReviewCommand:
    task_id: str
    reviewer: str
    verdict: str
    report_path: str
    reviewed_head_sha: str
    finding_count: int = 0
    blocking_finding_count: int = 0
    summary: str | None = None


__all__ = ["RecordExternalReviewCommand"]
