from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol, TypeAlias


TaskRecord: TypeAlias = dict[str, Any]
TaskMutator: TypeAlias = Callable[[TaskRecord], TaskRecord | None]


@dataclass(frozen=True, slots=True)
class ConformanceCheck:
    status: str
    summary: str


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    provider: str
    task_id: str
    agent_id: str
    role: str
    instruction: str


@dataclass(frozen=True, slots=True)
class VerificationResult:
    gates: tuple[Mapping[str, object], ...]


@dataclass(frozen=True, slots=True)
class CloseoutResult:
    closed: bool
    status: str | None = None
    gates: tuple[Mapping[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowEvent:
    event_type: str
    source: Mapping[str, object]
    data: Mapping[str, object]


class TaskRecordPort(Protocol):
    def load(self, task_id: str) -> TaskRecord: ...

    def list(self) -> tuple[TaskRecord, ...]: ...

    def save(self, task: TaskRecord) -> None: ...

    def update(self, task_id: str, mutator: TaskMutator) -> TaskRecord: ...


class WorkflowPlanningPort(Protocol):
    def freeze_spec(self, task_id: str) -> None: ...

    def generate_subtasks(self, task_id: str) -> None: ...


class FeatureObligationPort(Protocol):
    def converge(self, task_id: str) -> bool: ...


class ConformancePort(Protocol):
    def pre_execution(
        self,
        task: TaskRecord,
        *,
        subtask_id: str,
        source: str,
    ) -> ConformanceCheck: ...

    def post_execution(
        self,
        task: TaskRecord,
        *,
        subtask_id: str,
        exit_code: int,
        source: str,
    ) -> ConformanceCheck: ...

    def execution_contract(self, task: TaskRecord, subtask: Mapping[str, object]) -> str: ...

    def write_log(self, task: TaskRecord) -> None: ...

    def status(self, task: TaskRecord) -> str: ...


class ProviderPort(Protocol):
    def run(self, request: ProviderRequest) -> int: ...


class VerificationPort(Protocol):
    def verify(self, task_id: str) -> VerificationResult: ...


class CloseoutPort(Protocol):
    def close(self, task_id: str, *, allow_dirty: bool) -> CloseoutResult: ...


class EventPublisherPort(Protocol):
    def publish(self, event: WorkflowEvent) -> None: ...


class ManualInterventionPort(Protocol):
    def required(
        self,
        *,
        task_id: str,
        reason: str,
        workflow_phase: str,
        status: str,
        detail: str,
    ) -> None: ...


__all__ = [
    "CloseoutPort",
    "CloseoutResult",
    "ConformanceCheck",
    "ConformancePort",
    "EventPublisherPort",
    "FeatureObligationPort",
    "ManualInterventionPort",
    "ProviderPort",
    "ProviderRequest",
    "TaskMutator",
    "TaskRecord",
    "TaskRecordPort",
    "VerificationPort",
    "VerificationResult",
    "WorkflowEvent",
    "WorkflowPlanningPort",
]
