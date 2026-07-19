from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..commands.agent import RegisterAgentCommand, UpdateAgentCommand
from ..results.agent import AgentView


class ProcessStartError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProcessExecutionRequest:
    command: tuple[str, ...]
    cwd: str
    stdin_text: str | None
    env: tuple[tuple[str, str], ...]
    heartbeat_seconds: int


@dataclass(frozen=True, slots=True)
class ProcessExecution:
    exit_code: int
    output_summary: str | None


class ProcessObserver(Protocol):
    def started(self, pid: int) -> None: ...

    def heartbeat(self, output_summary: str | None) -> bool: ...


class AgentTrackingPort(Protocol):
    def register(self, command: RegisterAgentCommand) -> AgentView: ...

    def update(self, command: UpdateAgentCommand) -> AgentView: ...


class AgentProcessPort(Protocol):
    def run(
        self,
        request: ProcessExecutionRequest,
        observer: ProcessObserver,
    ) -> ProcessExecution: ...


__all__ = [
    "AgentProcessPort",
    "AgentTrackingPort",
    "ProcessExecution",
    "ProcessExecutionRequest",
    "ProcessObserver",
    "ProcessStartError",
]
