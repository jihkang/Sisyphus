from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentExecutionResult:
    task_id: str
    agent_id: str
    exit_code: int
    status: str


__all__ = ["AgentExecutionResult"]
