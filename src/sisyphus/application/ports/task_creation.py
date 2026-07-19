from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..commands.task import CreateTaskRecordCommand
from .workflow import TaskRecord


class TaskFactoryPort(Protocol):
    def build(self, command: CreateTaskRecordCommand) -> TaskRecord: ...


class TaskTemplatePort(Protocol):
    def materialize(self, task: TaskRecord) -> None: ...


class TaskWorkspacePort(Protocol):
    def task_directory_exists(self, task: TaskRecord) -> bool: ...

    def task_file(self, task: TaskRecord) -> Path: ...

    def create_worktree(self, task: TaskRecord) -> None: ...

    def create_task_directory(self, task: TaskRecord) -> None: ...

    def rollback(self, task: TaskRecord) -> tuple[str, ...]: ...


class TaskWorkspaceProvisioningError(RuntimeError):
    pass


__all__ = [
    "TaskFactoryPort",
    "TaskTemplatePort",
    "TaskWorkspacePort",
    "TaskWorkspaceProvisioningError",
]
