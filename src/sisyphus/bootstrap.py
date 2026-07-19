from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .application import AgentQueryService, LifecycleApplicationService, TaskQueryService
from .application.use_cases import WorkflowService
from .infra.config.loader import SisyphusConfig
from .infra.orchestration.workflow_adapters import (
    CloseoutAdapter,
    ConformanceAdapter,
    EventPublisherAdapter,
    FeatureObligationAdapter,
    FileTaskRecordAdapter,
    ManualInterventionAdapter,
    PlanningWorkflowAdapter,
    ProviderAdapter,
    ProviderRunner,
    VerificationAdapter,
)
from .infra.persistence.repositories import JsonAgentRepository, JsonTaskRepository


@dataclass(frozen=True, slots=True)
class Application:
    tasks: TaskQueryService
    agents: AgentQueryService
    lifecycle: LifecycleApplicationService


def build_application(repo_root: Path, task_dir_name: str) -> Application:
    task_repository = JsonTaskRepository(repo_root, task_dir_name)
    agent_repository = JsonAgentRepository(repo_root, task_dir_name)
    return Application(
        tasks=TaskQueryService(task_repository),
        agents=AgentQueryService(agent_repository),
        lifecycle=LifecycleApplicationService(),
    )


def build_workflow_service(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    provider_runner: ProviderRunner,
) -> WorkflowService:
    return WorkflowService(
        tasks=FileTaskRecordAdapter(repo_root, config),
        planning=PlanningWorkflowAdapter(repo_root, config),
        obligations=FeatureObligationAdapter(repo_root, config),
        conformance=ConformanceAdapter(repo_root, config),
        provider=ProviderAdapter(repo_root, provider_runner),
        verification=VerificationAdapter(repo_root, config),
        closeout=CloseoutAdapter(repo_root, config),
        events=EventPublisherAdapter(repo_root, config),
        interventions=ManualInterventionAdapter(repo_root, config),
    )


__all__ = ["Application", "build_application", "build_workflow_service"]
