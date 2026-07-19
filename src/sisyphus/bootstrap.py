from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .application import AgentQueryService, LifecycleApplicationService, TaskQueryService
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


__all__ = ["Application", "build_application"]
