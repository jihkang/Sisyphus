from __future__ import annotations

from dataclasses import dataclass

from ...domain.verification import CommandExecution
from .artifacts import ArtifactRef


@dataclass(frozen=True, slots=True)
class VerificationOutcome:
    task_id: str
    status: str
    stage: str
    audit_attempts: int
    max_audit_attempts: int
    gates: tuple[dict, ...]
    command_results: tuple[CommandExecution, ...]
    verify_artifact: ArtifactRef


__all__ = ["VerificationOutcome"]
