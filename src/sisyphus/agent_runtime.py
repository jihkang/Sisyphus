from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess  # Compatibility patch point for existing callers and tests.

from .agents import AgentTrackingError
from .application.commands.agent import RunTrackedAgentCommand
from .application.use_cases.agent_execution import AgentExecutionError
from .application.use_cases.agents import AgentManagementError
from .composition.agent_execution import build_agent_execution_service
from .config import SisyphusConfig
from .domain.agent import AgentPolicyError
from .infra.execution import OutputTracker


@dataclass(slots=True)
class AgentRunOutcome:
    task_id: str
    agent_id: str
    exit_code: int
    status: str


def run_tracked_agent(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    agent_id: str,
    role: str,
    provider: str,
    command: list[str],
    *,
    current_step: str | None = None,
    last_message_summary: str | None = None,
    owned_paths: list[str] | None = None,
    heartbeat_seconds: int = 10,
    run_cwd: Path | None = None,
    stdin_text: str | None = None,
    env: dict[str, str] | None = None,
) -> AgentRunOutcome:
    try:
        result = build_agent_execution_service(
            repo_root,
            config,
        ).run(
            RunTrackedAgentCommand(
                task_id=task_id,
                agent_id=agent_id,
                role=role,
                provider=provider,
                command=tuple(command),
                current_step=current_step,
                last_message_summary=last_message_summary,
                owned_paths=tuple(owned_paths or ()),
                heartbeat_seconds=heartbeat_seconds,
                run_cwd=str(run_cwd or Path.cwd()),
                stdin_text=stdin_text,
                env=tuple((env or {}).items()),
            )
        )
    except (AgentExecutionError, AgentManagementError, AgentPolicyError) as error:
        raise AgentTrackingError(str(error)) from error
    return AgentRunOutcome(
        task_id=result.task_id,
        agent_id=result.agent_id,
        exit_code=result.exit_code,
        status=result.status,
    )


__all__ = ["AgentRunOutcome", "OutputTracker", "run_tracked_agent"]
