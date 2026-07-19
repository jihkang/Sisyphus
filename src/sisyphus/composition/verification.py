from __future__ import annotations

from pathlib import Path

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


__all__ = ["build_verification_service"]
