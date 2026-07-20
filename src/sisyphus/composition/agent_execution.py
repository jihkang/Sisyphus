from __future__ import annotations

from pathlib import Path

from ..application.use_cases.agent_execution import AgentExecutionService
from ..config import SisyphusConfig
from ..infra.execution import TrackedSubprocessAdapter
from .agents import build_agent_management_service


def build_agent_execution_service(
    repo_root: Path,
    config: SisyphusConfig,
) -> AgentExecutionService:
    return AgentExecutionService(
        tracking=build_agent_management_service(repo_root, config),
        processes=TrackedSubprocessAdapter(),
    )


__all__ = ["build_agent_execution_service"]
