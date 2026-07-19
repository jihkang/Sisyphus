from __future__ import annotations

from typing import Protocol

from ..commands.task import CreateTaskRecordCommand
from .workflow import TaskRecord


class TaskFactoryPort(Protocol):
    def build(self, command: CreateTaskRecordCommand) -> TaskRecord: ...


__all__ = ["TaskFactoryPort"]
