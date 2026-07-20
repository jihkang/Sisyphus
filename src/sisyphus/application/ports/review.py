from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


class ExternalReviewEvidenceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExternalReviewFinding:
    finding_id: str
    severity: str
    title: str
    detail: str
    blocking: bool


@dataclass(frozen=True, slots=True)
class ExternalReviewScopeEvidence:
    current_head_sha: str
    scope_digest: str
    document_digests: tuple[tuple[str, str | None], ...]


@dataclass(frozen=True, slots=True)
class ExternalReviewEvidence:
    envelope_path: str
    envelope_digest: str
    envelope_size_bytes: int
    provider: str
    reviewer: str
    reviewed_head_sha: str
    scope_digest: str
    report_path: str
    report_digest: str
    report_size_bytes: int
    summary: str
    findings: tuple[ExternalReviewFinding, ...]
    current_head_sha: str
    current_scope_digest: str
    document_digests: tuple[tuple[str, str | None], ...]
    dirty_paths: tuple[str, ...]

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def blocking_finding_count(self) -> int:
        return sum(1 for finding in self.findings if finding.blocking)

    @property
    def status(self) -> str:
        return "failed" if self.blocking_finding_count else "passed"


class ExternalReviewEvidencePort(Protocol):
    def scope(
        self,
        workspace: str,
        task: Mapping[str, object],
    ) -> ExternalReviewScopeEvidence: ...

    def inspect(
        self,
        workspace: str,
        envelope_path: str,
        task: Mapping[str, object],
    ) -> ExternalReviewEvidence: ...


__all__ = [
    "ExternalReviewEvidence",
    "ExternalReviewEvidenceError",
    "ExternalReviewEvidencePort",
    "ExternalReviewFinding",
    "ExternalReviewScopeEvidence",
]
