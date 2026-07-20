from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExternalReviewRecordResult:
    task_id: str
    status: str
    provider: str
    reviewer: str
    reviewed_head_sha: str
    report_path: str
    report_digest: str
    finding_count: int
    blocking_finding_count: int
    completed_at: str


__all__ = ["ExternalReviewRecordResult"]
