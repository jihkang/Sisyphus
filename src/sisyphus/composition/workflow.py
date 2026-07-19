from __future__ import annotations

from pathlib import Path

from ..application.use_cases.workflow import WorkflowService
from ..infra.config.loader import SisyphusConfig
from ..infra.orchestration.common_adapters import FileTaskRecordAdapter, ManualInterventionAdapter
from ..infra.orchestration.workflow_adapters import (
    CloseoutAdapter,
    ConformanceAdapter,
    EventPublisherAdapter,
    FeatureObligationAdapter,
    PlanningWorkflowAdapter,
    ProviderAdapter,
    ProviderRunner,
    VerificationAdapter,
)
from .planning import build_planning_service


def build_workflow_service(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    provider_runner: ProviderRunner,
) -> WorkflowService:
    return WorkflowService(
        tasks=FileTaskRecordAdapter(repo_root, config),
        planning=PlanningWorkflowAdapter(build_planning_service(repo_root, config)),
        obligations=FeatureObligationAdapter(repo_root, config),
        conformance=ConformanceAdapter(repo_root, config),
        provider=ProviderAdapter(repo_root, provider_runner),
        verification=VerificationAdapter(repo_root, config),
        closeout=CloseoutAdapter(repo_root, config),
        events=EventPublisherAdapter(repo_root, config),
        interventions=ManualInterventionAdapter(repo_root, config),
    )


__all__ = ["build_workflow_service"]
