from __future__ import annotations

from pathlib import Path

from ..application.use_cases.agent_launch import AgentLaunchService
from ..config import SisyphusConfig
from .agent_execution import build_agent_execution_service
from .planning import build_planning_service


def build_agent_launch_service(
    repo_root: Path,
    config: SisyphusConfig,
) -> AgentLaunchService:
    return AgentLaunchService(
        planning=build_planning_service(repo_root, config),
        execution=build_agent_execution_service(repo_root, config),
    )


__all__ = ["build_agent_launch_service"]
