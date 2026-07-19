from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import shutil

from ...application.ports.task_creation import TaskWorkspaceProvisioningError
from ...application.ports.workflow import TaskRecord
from ...gitops import (
    GitOperationError,
    create_task_branch_and_worktree,
    remove_task_branch_and_worktree,
)


TemplateMaterializer = Callable[[TaskRecord], None]


class RepositoryTaskTemplateAdapter:
    def __init__(self, materialize: TemplateMaterializer) -> None:
        self._materialize = materialize

    def materialize(self, task: TaskRecord) -> None:
        self._materialize(task)


class RepositoryTaskWorkspaceAdapter:
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    def task_directory_exists(self, task: TaskRecord) -> bool:
        return self._task_path(task).exists()

    def task_file(self, task: TaskRecord) -> Path:
        return self._task_path(task) / "task.json"

    def create_worktree(self, task: TaskRecord) -> None:
        try:
            create_task_branch_and_worktree(
                repo_root=self._repo_root,
                branch=str(task["branch"]),
                target_path=Path(str(task["worktree_path"])),
                base_branch=str(task["base_branch"]),
            )
        except GitOperationError as exc:
            raise TaskWorkspaceProvisioningError(str(exc)) from exc

    def create_task_directory(self, task: TaskRecord) -> None:
        self._task_path(task).mkdir(parents=True, exist_ok=False)

    def rollback(self, task: TaskRecord) -> tuple[str, ...]:
        errors: list[str] = []
        task_path = self._task_path(task)
        if task_path.exists():
            try:
                shutil.rmtree(task_path)
            except OSError as exc:
                errors.append(f"failed to remove task directory {task_path}: {exc}")
        try:
            remove_task_branch_and_worktree(
                repo_root=self._repo_root,
                branch=str(task["branch"]),
                target_path=Path(str(task["worktree_path"])),
            )
        except GitOperationError as exc:
            errors.append(str(exc))
        return tuple(errors)

    def _task_path(self, task: TaskRecord) -> Path:
        return self._repo_root / str(task["task_dir"])


__all__ = [
    "RepositoryTaskTemplateAdapter",
    "RepositoryTaskWorkspaceAdapter",
    "TemplateMaterializer",
]
