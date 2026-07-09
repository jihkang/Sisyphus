from __future__ import annotations

from pathlib import Path
import json
import sys

from ....agent_runtime import run_tracked_agent
from ....agents import AgentTrackingError, list_agents, register_agent, update_agent
from ....config import SisyphusConfig
from ....planning import enforce_plan_approved, enforce_spec_frozen


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
        agent = register_agent(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            agent_id=agent_id,
            role=role,
            provider=provider,
            current_step=step,
            last_message_summary=summary,
            owned_paths=owned_paths,
            status=status,
        )
    except (AgentTrackingError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

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
        agent = update_agent(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            agent_id=agent_id,
            status=status,
            provider=provider,
            current_step=step,
            last_message_summary=summary,
            owned_paths=owned_paths,
            command=command,
            pid=pid,
            error=error,
        )
    except (AgentTrackingError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

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
    if role == "worker":
        approved, task = enforce_plan_approved(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            action="execution",
        )
        if not approved:
            plan_gates = [gate for gate in task.get("gates", []) if gate.get("source") == "plan"]
            message = plan_gates[0]["message"] if plan_gates else "task plan approval required before execution"
            print(f"error: {message}", file=sys.stderr)
            return 1
        frozen, task = enforce_spec_frozen(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            action="execution",
        )
        if not frozen:
            spec_gates = [gate for gate in task.get("gates", []) if gate.get("source") == "spec"]
            message = spec_gates[0]["message"] if spec_gates else "task spec must be frozen before execution"
            print(f"error: {message}", file=sys.stderr)
            return 1
    try:
        outcome = run_tracked_agent(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            agent_id=agent_id,
            role=role,
            provider=provider,
            command=command,
            current_step=step,
            last_message_summary=summary,
            owned_paths=owned_paths,
            heartbeat_seconds=heartbeat_seconds,
            run_cwd=repo_root,
            stdin_text=stdin_text,
            env=env,
        )
    except (AgentTrackingError, FileNotFoundError) as exc:
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
