from __future__ import annotations

from pathlib import Path

from ..application.use_cases.agents import AgentManagementService
from ..config import SisyphusConfig
from ..infra.clock import SystemClock
from ..infra.persistence.repositories import JsonAgentRepository, JsonTaskRepository


def build_agent_management_service(
    repo_root: Path,
    config: SisyphusConfig,
) -> AgentManagementService:
    return AgentManagementService(
        tasks=JsonTaskRepository(repo_root, config.task_dir),
        agents=JsonAgentRepository(repo_root, config.task_dir),
        clock=SystemClock(),
    )


__all__ = ["build_agent_management_service"]
