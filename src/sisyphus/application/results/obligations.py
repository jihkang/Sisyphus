from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ObligationQueueMaterialization:
    task_id: str
    queue_path: Path
    changed: bool
    obligation_count: int


@dataclass(frozen=True, slots=True)
class ObligationExecutionResult:
    task_id: str
    obligation_id: str | None
    executed: bool
    status: str
    queue_path: Path
    message: str | None = None


@dataclass(frozen=True, slots=True)
class ObligationConvergenceResult:
    task_id: str
    progressed: bool
    converged: bool
    step_count: int
    executed_count: int
    last_status: str
    message: str | None = None


__all__ = [
    "ObligationConvergenceResult",
    "ObligationExecutionResult",
    "ObligationQueueMaterialization",
]
