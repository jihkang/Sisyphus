from __future__ import annotations

from pathlib import Path
import json
import sys

from ....application.commands.agent import (
    RegisterAgentCommand,
    RunTrackedAgentCommand,
    UpdateAgentCommand,
)
from ....application.use_cases.agent_launch import AgentLaunchError
from ....application.use_cases.agents import AgentManagementError
from ....composition.agents import build_agent_management_service
from ....composition.agent_launch import build_agent_launch_service
from ....config import SisyphusConfig
from ....domain.agent import AgentPolicyError
from ...agent_presenter import present_agent
from ...agent_queries import list_agents


def handle_agents(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str | None,
    as_json: bool,
    stale_after_seconds: int,
) -> int:
    agents = list_agents(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        stale_after_seconds=stale_after_seconds,
    )

    if as_json:
        print(json.dumps(agents, indent=2))
        return 0

    if not agents:
        print("no agents found")
        return 0

    for agent in agents:
        print(
            f"{agent.get('agent_id')} "
            f"task={agent.get('parent_task_id')} "
            f"provider={agent.get('provider') or 'n/a'} "
            f"role={agent.get('role')} "
            f"status={agent.get('status')}"
        )
        if agent.get("pid") is not None:
            print(f"  pid: {agent['pid']}")
        if agent.get("current_step"):
            print(f"  step: {agent['current_step']}")
        if agent.get("last_message_summary"):
            print(f"  summary: {agent['last_message_summary']}")
        if agent.get("owned_paths"):
            print(f"  owned_paths: {', '.join(agent['owned_paths'])}")
        if agent.get("command"):
            print(f"  command: {' '.join(agent['command'])}")
        if agent.get("error"):
            print(f"  error: {agent['error']}")
    return 0


def handle_agent_start(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    agent_id: str,
    role: str,
    status: str,
    provider: str | None,
    step: str | None,
    summary: str | None,
    owned_paths: list[str] | None,
) -> int:
    try:
        view = build_agent_management_service(repo_root, config).register(
            RegisterAgentCommand(
                task_id=task_id,
                agent_id=agent_id,
                role=role,
                provider=provider,
                current_step=step,
                last_message_summary=summary,
                owned_paths=tuple(owned_paths or ()),
                status=status,
            )
        )
    except (AgentManagementError, AgentPolicyError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    agent = present_agent(view)

    print(f"agent {agent['agent_id']}")
    print(f"task: {agent['parent_task_id']}")
    print(f"status: {agent['status']}")
    return 0


def handle_agent_update(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    agent_id: str,
    status: str | None,
    provider: str | None,
    step: str | None,
    summary: str | None,
    owned_paths: list[str] | None,
    command: list[str] | None,
    pid: int | None,
    error: str | None,
) -> int:
    try:
        view = build_agent_management_service(repo_root, config).update(
            UpdateAgentCommand(
                task_id=task_id,
                agent_id=agent_id,
                status=status,
                provider=provider,
                current_step=step,
                last_message_summary=summary,
                owned_paths=tuple(owned_paths) if owned_paths is not None else None,
                command=tuple(command) if command is not None else None,
                pid=pid,
                error=error,
            )
        )
    except (AgentManagementError, AgentPolicyError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    agent = present_agent(view)

    print(f"agent {agent['agent_id']}")
    print(f"task: {agent['parent_task_id']}")
    print(f"status: {agent['status']}")
    return 0


def handle_agent_finish(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    agent_id: str,
    status: str,
    summary: str | None,
    error: str | None,
) -> int:
    return handle_agent_update(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        agent_id=agent_id,
        status=status,
        provider=None,
        step=None,
        summary=summary,
        owned_paths=None,
        command=None,
        pid=None,
        error=error,
    )


def handle_agent_run(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    agent_id: str,
    role: str,
    provider: str,
    step: str | None,
    summary: str | None,
    owned_paths: list[str] | None,
    heartbeat_seconds: int,
    command: list[str],
    stdin_text: str | None = None,
    env: dict[str, str] | None = None,
) -> int:
    if command and command[0] == "--":
        command = command[1:]
    try:
        outcome = build_agent_launch_service(repo_root, config).run(
            RunTrackedAgentCommand(
                task_id=task_id,
                agent_id=agent_id,
                role=role,
                provider=provider,
                command=tuple(command),
                current_step=step,
                last_message_summary=summary,
                owned_paths=tuple(owned_paths or ()),
                heartbeat_seconds=heartbeat_seconds,
                run_cwd=str(repo_root),
                stdin_text=stdin_text,
                env=tuple((env or {}).items()),
            )
        )
    except (AgentLaunchError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"agent {outcome.agent_id}")
    print(f"task: {outcome.task_id}")
    print(f"status: {outcome.status}")
    print(f"exit_code: {outcome.exit_code}")
    return outcome.exit_code


__all__ = [
    "handle_agent_finish",
    "handle_agent_run",
    "handle_agent_start",
    "handle_agent_update",
    "handle_agents",
]
