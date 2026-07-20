from __future__ import annotations

from pathlib import Path

from ..application.commands.review import RecordExternalReviewCommand
from ..application.results.review import ExternalReviewRecordResult, ExternalReviewScopeResult
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
    envelope_path: str,
) -> ExternalReviewRecordResult:
    return build_external_review_service(repo_root, config).record(
        RecordExternalReviewCommand(
            task_id=task_id,
            envelope_path=envelope_path,
        )
    )


def external_review_scope(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
) -> ExternalReviewScopeResult:
    return build_external_review_service(repo_root, config).scope(task_id)


__all__ = [
    "build_external_review_service",
    "external_review_scope",
    "record_external_review",
]
