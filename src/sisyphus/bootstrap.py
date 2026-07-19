from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .application import AgentQueryService, LifecycleApplicationService, TaskQueryService
from .composition.agent_execution import build_agent_execution_service
from .composition.agent_launch import build_agent_launch_service
from .composition.agents import build_agent_management_service
from .composition.planning import build_planning_service
from .composition.promotion import build_promotion_service
from .composition.verification import build_verification_service
from .composition.workflow import build_workflow_service
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


__all__ = [
    "Application",
    "build_application",
    "build_agent_execution_service",
    "build_agent_launch_service",
    "build_agent_management_service",
    "build_planning_service",
    "build_promotion_service",
    "build_verification_service",
    "build_workflow_service",
]
