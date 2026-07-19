from __future__ import annotations

from typing import Protocol

from ...domain.agent.models import Agent
from ...domain.task.models import Task


class TaskRepository(Protocol):
    def get(self, task_id: str) -> Task: ...

    def save(self, task: Task) -> Task: ...


class AgentRepository(Protocol):
    def get(self, task_id: str, agent_id: str) -> Agent: ...

    def save(self, agent: Agent) -> Agent: ...


__all__ = ["AgentRepository", "TaskRepository"]
