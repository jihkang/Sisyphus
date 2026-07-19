from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegisterAgentCommand:
    task_id: str
    agent_id: str
    role: str
    provider: str | None = None
    current_step: str | None = None
    last_message_summary: str | None = None
    owned_paths: tuple[str, ...] = ()
    command: tuple[str, ...] = ()
    status: str = "running"


@dataclass(frozen=True, slots=True)
class UpdateAgentCommand:
    task_id: str
    agent_id: str
    status: str | None = None
    provider: str | None = None
    current_step: str | None = None
    last_message_summary: str | None = None
    owned_paths: tuple[str, ...] | None = None
    command: tuple[str, ...] | None = None
    pid: int | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class RunTrackedAgentCommand:
    task_id: str
    agent_id: str
    role: str
    provider: str
    command: tuple[str, ...]
    current_step: str | None = None
    last_message_summary: str | None = None
    owned_paths: tuple[str, ...] = ()
    heartbeat_seconds: int = 10
    run_cwd: str | None = None
    stdin_text: str | None = None
    env: tuple[tuple[str, str], ...] = ()


__all__ = ["RegisterAgentCommand", "RunTrackedAgentCommand", "UpdateAgentCommand"]
