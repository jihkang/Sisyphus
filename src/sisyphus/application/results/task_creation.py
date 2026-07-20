from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..ports.workflow import TaskRecord


@dataclass(slots=True)
class CreateOutcome:
    task: TaskRecord
    task_file: Path


__all__ = ["CreateOutcome"]
