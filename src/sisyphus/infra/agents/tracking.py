from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ...application.ports.agent_execution import AgentRegistration, AgentTrackingUpdate
from ...config import SisyphusConfig


RegisterAgent = Callable[..., dict]
UpdateAgent = Callable[..., dict]


class FunctionAgentTrackingAdapter:
    def __init__(
        self,
        repo_root: Path,
        config: SisyphusConfig,
        *,
        register_agent: RegisterAgent,
        update_agent: UpdateAgent,
        heartbeat_errors: tuple[type[BaseException], ...],
    ) -> None:
        self._repo_root = repo_root
        self._config = config
        self._register_agent = register_agent
        self._update_agent = update_agent
        self._heartbeat_errors = heartbeat_errors

    def register(self, registration: AgentRegistration) -> None:
        self._register_agent(
            repo_root=self._repo_root,
            config=self._config,
            task_id=registration.task_id,
            agent_id=registration.agent_id,
            role=registration.role,
            provider=registration.provider,
            current_step=registration.current_step,
            last_message_summary=registration.last_message_summary,
            owned_paths=list(registration.owned_paths),
            command=list(registration.command),
            status="running",
        )

    def update(self, update: AgentTrackingUpdate) -> None:
        self._update_agent(**self._kwargs(update))

    def heartbeat(self, update: AgentTrackingUpdate) -> bool:
        try:
            self.update(update)
        except self._heartbeat_errors:
            return False
        return True

    def _kwargs(self, update: AgentTrackingUpdate) -> dict[str, object]:
        return {
            "repo_root": self._repo_root,
            "config": self._config,
            "task_id": update.task_id,
            "agent_id": update.agent_id,
            "provider": update.provider,
            "command": list(update.command),
            "current_step": update.current_step,
            "last_message_summary": update.last_message_summary,
            "pid": update.pid,
            "status": update.status,
            "error": update.error,
        }


__all__ = ["FunctionAgentTrackingAdapter", "RegisterAgent", "UpdateAgent"]
