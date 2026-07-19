from __future__ import annotations

from dataclasses import dataclass


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


__all__ = ["RunTrackedAgentCommand"]
