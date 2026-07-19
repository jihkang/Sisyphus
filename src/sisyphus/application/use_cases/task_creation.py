from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..commands.task import CreateTaskRecordCommand
from ..ports.task_creation import (
    TaskFactoryPort,
    TaskTemplatePort,
    TaskWorkspacePort,
    TaskWorkspaceProvisioningError,
)
from ..ports.workflow import TaskRecord, TaskRecordPort
from ..results.task_creation import CreateOutcome


class TaskCreationError(RuntimeError):
    """Raised when a task workspace cannot be provisioned atomically."""


@dataclass(slots=True)
class TaskRecordCreationService:
    factory: TaskFactoryPort
    tasks: TaskRecordPort

    def create(self, command: CreateTaskRecordCommand) -> TaskRecord:
        task = self.factory.build(command)
        self.tasks.save(task)
        return task


@dataclass(slots=True)
class TaskWorkspaceCreationService:
    factory: TaskFactoryPort
    tasks: TaskRecordPort
    workspace: TaskWorkspacePort
    templates: TaskTemplatePort

    def create(self, command: CreateTaskRecordCommand) -> CreateOutcome:
        task = self.factory.build(command)
        task_file = self.workspace.task_file(task)
        if self.workspace.task_directory_exists(task):
            raise TaskCreationError(self._existing_task_error(task, task_file.parent))

        try:
            self.workspace.create_worktree(task)
        except TaskWorkspaceProvisioningError as exc:
            raise TaskCreationError(str(exc)) from exc

        try:
            self.workspace.create_task_directory(task)
            self.tasks.save(task)
            self.templates.materialize(task)
        except Exception as exc:
            rollback_errors = self.workspace.rollback(task)
            if rollback_errors:
                details = "; ".join(rollback_errors)
                raise TaskCreationError(
                    f"task creation failed and rollback was incomplete: {details}"
                ) from exc
            raise TaskCreationError(f"task creation failed: {exc}") from exc

        return CreateOutcome(task=task, task_file=task_file)

    def _existing_task_error(self, task: TaskRecord, task_path: Path) -> str:
        try:
            existing = self.tasks.load(str(task["id"]))
        except (FileNotFoundError, OSError, ValueError):
            return f"task already exists: {task['id']} (task_dir: {task_path})"

        status = str(existing.get("status", "unknown"))
        branch = str(existing.get("branch", "unknown"))
        worktree_path = str(existing.get("worktree_path", "unknown"))
        if status == "closed":
            suggested_slug = _suggest_followup_slug(
                str(existing.get("slug") or task.get("slug") or "followup")
            )
            return (
                f"task already exists: {task['id']} "
                f"(status: {status}, branch: {branch}, task_dir: {task_path}, "
                f"worktree_path: {worktree_path}); create a follow-up task with a new slug "
                f"such as `{suggested_slug}`"
            )
        return (
            f"task already exists: {task['id']} "
            f"(status: {status}, branch: {branch}, task_dir: {task_path}, "
            f"worktree_path: {worktree_path}); use a new slug to create another task"
        )


def _suggest_followup_slug(slug: str) -> str:
    cleaned = slug.strip("-") or "followup"
    return f"{cleaned}-followup"


__all__ = [
    "TaskCreationError",
    "TaskRecordCreationService",
    "TaskWorkspaceCreationService",
]
