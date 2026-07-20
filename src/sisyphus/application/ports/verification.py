from __future__ import annotations

from typing import Protocol

from ...domain.lifecycle import ConformanceState
from ...domain.verification import CommandExecution
from ..results.artifacts import ArtifactRef
from .workflow import TaskRecord


class VerificationCommandPort(Protocol):
    def run(self, task_id: str, commands: tuple[str, ...]) -> tuple[CommandExecution, ...]: ...


class VerificationDocumentPort(Protocol):
    def read(self, task_id: str, relative_path: str) -> str | None: ...

    def write(self, task_id: str, relative_path: str, content: str) -> ArtifactRef: ...


class VerificationEvidencePort(Protocol):
    def write(
        self,
        task_id: str,
        task: TaskRecord,
        command_results: tuple[CommandExecution, ...],
    ) -> None: ...


EvidenceGraphPort = VerificationEvidencePort


class VerificationConformancePort(Protocol):
    def snapshot(self, task: TaskRecord) -> ConformanceState: ...

    def append(
        self,
        task: TaskRecord,
        *,
        checkpoint_type: str,
        status: str,
        summary: str,
        source: str,
        resolved: bool,
        drift: int,
    ) -> TaskRecord: ...


__all__ = [
    "EvidenceGraphPort",
    "VerificationCommandPort",
    "VerificationConformancePort",
    "VerificationDocumentPort",
    "VerificationEvidencePort",
]
