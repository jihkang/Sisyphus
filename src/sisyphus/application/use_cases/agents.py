from __future__ import annotations

from dataclasses import dataclass

from ...domain.agent import (
    Agent,
    create_agent,
    effective_agent_status,
    update_agent_state,
    validate_agent_id,
)
from ..commands.agent import RegisterAgentCommand, UpdateAgentCommand
from ..ports.clock import ClockPort
from ..ports.repositories import AgentRepository, TaskRepository
from ..results.agent import AgentView


class AgentManagementError(RuntimeError):
    pass


@dataclass(slots=True)
class AgentManagementService:
    tasks: TaskRepository
    agents: AgentRepository
    clock: ClockPort

    def register(self, command: RegisterAgentCommand) -> AgentView:
        validate_agent_id(command.agent_id)
        self.tasks.get(command.task_id)
        if self.agents.exists(command.task_id, command.agent_id):
            raise AgentManagementError(f"agent already exists: {command.agent_id}")
        agent = create_agent(
            task_id=command.task_id,
            agent_id=command.agent_id,
            role=command.role,
            provider=command.provider,
            status=command.status,
            current_step=command.current_step,
            last_message_summary=command.last_message_summary,
            owned_paths=command.owned_paths,
            command=command.command,
            now=self.clock.now(),
        )
        self.agents.save(agent)
        return self._view(agent, stale_after_seconds=None)

    def update(self, command: UpdateAgentCommand) -> AgentView:
        validate_agent_id(command.agent_id)
        if not self.agents.exists(command.task_id, command.agent_id):
            raise FileNotFoundError(f"agent not found: {command.agent_id}")
        agent = self.agents.get(command.task_id, command.agent_id)
        changes = {
            "status": command.status,
            "provider": command.provider,
            "current_step": command.current_step,
            "last_message_summary": command.last_message_summary,
            "owned_paths": command.owned_paths,
            "command": command.command,
            "pid": command.pid,
            "error": command.error,
        }
        updated = update_agent_state(agent, changes, now=self.clock.now())
        self.agents.save(updated)
        return self._view(updated, stale_after_seconds=None)

    def get(
        self,
        task_id: str,
        agent_id: str,
        *,
        stale_after_seconds: int | None,
    ) -> AgentView:
        validate_agent_id(agent_id)
        if not self.agents.exists(task_id, agent_id):
            raise FileNotFoundError(f"agent not found: {agent_id}")
        return self._view(
            self.agents.get(task_id, agent_id),
            stale_after_seconds=stale_after_seconds,
        )

    def list(
        self,
        *,
        task_id: str | None = None,
        stale_after_seconds: int | None,
    ) -> tuple[AgentView, ...]:
        views = [
            self._view(agent, stale_after_seconds=stale_after_seconds)
            for agent in self.agents.list(task_id=task_id)
        ]
        return tuple(
            sorted(
                views,
                key=lambda view: (
                    view.agent.updated_at or "",
                    view.agent.started_at or "",
                    view.agent.agent_id,
                ),
                reverse=True,
            )
        )

    def _view(self, agent: Agent, *, stale_after_seconds: int | None) -> AgentView:
        return AgentView(
            agent=agent,
            raw_status=agent.status,
            effective_status=effective_agent_status(
                agent,
                stale_after_seconds=stale_after_seconds,
                now=self.clock.now(),
            ),
        )


__all__ = ["AgentManagementError", "AgentManagementService"]
