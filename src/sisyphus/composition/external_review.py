from __future__ import annotations

from pathlib import Path

from ..application.commands.review import RecordExternalReviewCommand
from ..application.results.review import ExternalReviewRecordResult
from ..application.use_cases.external_review import ExternalReviewService
from ..infra.clock import SystemClock
from ..infra.config.loader import SisyphusConfig
from ..infra.orchestration.common_adapters import FileTaskRecordAdapter
from ..infra.verification.external_review import GitExternalReviewEvidenceAdapter


def build_external_review_service(
    repo_root: Path,
    config: SisyphusConfig,
) -> ExternalReviewService:
    return ExternalReviewService(
        tasks=FileTaskRecordAdapter(repo_root, config),
        evidence=GitExternalReviewEvidenceAdapter(),
        clock=SystemClock(),
    )


def record_external_review(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    reviewer: str,
    verdict: str,
    report_path: str,
    reviewed_head_sha: str,
    finding_count: int = 0,
    blocking_finding_count: int = 0,
    summary: str | None = None,
) -> ExternalReviewRecordResult:
    return build_external_review_service(repo_root, config).record(
        RecordExternalReviewCommand(
            task_id=task_id,
            reviewer=reviewer,
            verdict=verdict,
            report_path=report_path,
            reviewed_head_sha=reviewed_head_sha,
            finding_count=finding_count,
            blocking_finding_count=blocking_finding_count,
            summary=summary,
        )
    )


__all__ = ["build_external_review_service", "record_external_review"]
