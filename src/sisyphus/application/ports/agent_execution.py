from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ProcessStartError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AgentRegistration:
    task_id: str
    agent_id: str
    role: str
    provider: str
    current_step: str
    last_message_summary: str
    owned_paths: tuple[str, ...]
    command: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AgentTrackingUpdate:
    task_id: str
    agent_id: str
    status: str | None = None
    provider: str | None = None
    command: tuple[str, ...] = ()
    current_step: str | None = None
    last_message_summary: str | None = None
    pid: int | None = None
    error: str | None = None


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
    def register(self, registration: AgentRegistration) -> None: ...

    def update(self, update: AgentTrackingUpdate) -> None: ...

    def heartbeat(self, update: AgentTrackingUpdate) -> bool: ...


class AgentProcessPort(Protocol):
    def run(
        self,
        request: ProcessExecutionRequest,
        observer: ProcessObserver,
    ) -> ProcessExecution: ...


__all__ = [
    "AgentProcessPort",
    "AgentRegistration",
    "AgentTrackingPort",
    "AgentTrackingUpdate",
    "ProcessExecution",
    "ProcessExecutionRequest",
    "ProcessObserver",
    "ProcessStartError",
]
