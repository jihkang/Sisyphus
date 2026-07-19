from __future__ import annotations

from pathlib import Path

from ..application.results.verification import VerificationOutcome
from ..application.use_cases.verification import VerificationService
from ..infra.clock import SystemClock
from ..infra.config.loader import SisyphusConfig
from ..infra.orchestration.common_adapters import EventPublisherAdapter, FileTaskRecordAdapter
from ..infra.orchestration.planning_adapters import PlanningDocumentAdapter, SpecValidationAdapter
from ..infra.verification import (
    ConformanceVerificationAdapter,
    EvidenceGraphAdapter,
    FileVerificationDocumentAdapter,
    ShellVerificationCommandAdapter,
)
from ..shared.paths import contained_path, task_dir as resolve_task_dir


def build_verification_service(repo_root: Path, config: SisyphusConfig) -> VerificationService:
    clock = SystemClock()
    return VerificationService(
        tasks=FileTaskRecordAdapter(repo_root, config),
        planning_documents=PlanningDocumentAdapter(repo_root, config),
        documents=FileVerificationDocumentAdapter(repo_root, config),
        validation=SpecValidationAdapter(repo_root, config),
        conformance=ConformanceVerificationAdapter(clock),
        commands=ShellVerificationCommandAdapter(repo_root, config, clock),
        evidence=EvidenceGraphAdapter(repo_root, config, clock),
        events=EventPublisherAdapter(repo_root, config),
        clock=clock,
    )


def verify_task(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
) -> VerificationOutcome:
    return build_verification_service(repo_root, config).verify(task_id)


def resolve_verification_artifact_path(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    relative_path: str,
) -> Path:
    directory = resolve_task_dir(repo_root, config.task_dir, task_id)
    return contained_path(directory, relative_path, require_relative=True)


__all__ = [
    "build_verification_service",
    "resolve_verification_artifact_path",
    "verify_task",
]
