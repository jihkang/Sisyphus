from __future__ import annotations

from dataclasses import dataclass

from ...domain.agent import Agent


@dataclass(frozen=True, slots=True)
class AgentView:
    agent: Agent
    raw_status: str
    effective_status: str


@dataclass(frozen=True, slots=True)
class AgentExecutionResult:
    task_id: str
    agent_id: str
    exit_code: int
    status: str


__all__ = ["AgentExecutionResult", "AgentView"]
