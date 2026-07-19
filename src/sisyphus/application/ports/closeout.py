from __future__ import annotations

from typing import Protocol

from .workflow import TaskRecord


class CloseoutEvidencePort(Protocol):
    def collect_gates(self, task_id: str, task: TaskRecord) -> tuple[dict, ...]: ...


class WorktreeStatusPort(Protocol):
    def is_dirty(self, task: TaskRecord) -> bool: ...


__all__ = ["CloseoutEvidencePort", "WorktreeStatusPort"]
