from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..application.use_cases.agent_execution import AgentExecutionService
from ..config import SisyphusConfig
from ..infra.agents import FunctionAgentTrackingAdapter
from ..infra.execution import TrackedSubprocessAdapter


def build_agent_execution_service(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    register_agent: Callable[..., dict],
    update_agent: Callable[..., dict],
    heartbeat_errors: tuple[type[BaseException], ...],
) -> AgentExecutionService:
    return AgentExecutionService(
        tracking=FunctionAgentTrackingAdapter(
            repo_root,
            config,
            register_agent=register_agent,
            update_agent=update_agent,
            heartbeat_errors=heartbeat_errors,
        ),
        processes=TrackedSubprocessAdapter(),
    )


__all__ = ["build_agent_execution_service"]
