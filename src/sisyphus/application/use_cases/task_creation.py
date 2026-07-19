from __future__ import annotations

from dataclasses import dataclass

from ..commands.task import CreateTaskRecordCommand
from ..ports.task_creation import TaskFactoryPort
from ..ports.workflow import TaskRecord, TaskRecordPort


@dataclass(slots=True)
class TaskRecordCreationService:
    factory: TaskFactoryPort
    tasks: TaskRecordPort

    def create(self, command: CreateTaskRecordCommand) -> TaskRecord:
        task = self.factory.build(command)
        self.tasks.save(task)
        return task


__all__ = ["TaskRecordCreationService"]
