from __future__ import annotations

from dataclasses import dataclass

from ..domain.agent.models import Agent
from ..domain.lifecycle import (
    LifecycleAction,
    LifecycleSnapshot,
    TransitionDecision,
    evaluate_lifecycle_policy,
)
from ..domain.task.models import Task
from .ports import AgentRepository, TaskRepository


@dataclass(frozen=True, slots=True)
class TaskQueryService:
    repository: TaskRepository

    def get(self, task_id: str) -> Task:
        return self.repository.get(task_id)


@dataclass(frozen=True, slots=True)
class AgentQueryService:
    repository: AgentRepository

    def get(self, task_id: str, agent_id: str) -> Agent:
        return self.repository.get(task_id, agent_id)


class LifecycleApplicationService:
    @staticmethod
    def evaluate(
        snapshot: LifecycleSnapshot,
        action: LifecycleAction,
    ) -> TransitionDecision:
        return evaluate_lifecycle_policy(snapshot, action)


__all__ = [
    "AgentQueryService",
    "LifecycleApplicationService",
    "TaskQueryService",
]
