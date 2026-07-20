from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExternalReviewRecordResult:
    task_id: str
    status: str
    provider: str
    reviewer: str
    reviewed_head_sha: str
    scope_digest: str
    envelope_path: str
    envelope_digest: str
    report_path: str
    report_digest: str
    finding_count: int
    blocking_finding_count: int
    completed_at: str


@dataclass(frozen=True, slots=True)
class ExternalReviewScopeResult:
    task_id: str
    current_head_sha: str
    scope_digest: str
    document_digests: tuple[tuple[str, str | None], ...]


__all__ = ["ExternalReviewRecordResult", "ExternalReviewScopeResult"]
