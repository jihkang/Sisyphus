from __future__ import annotations

from pathlib import Path

from ...application.ports.workflow import TaskMutator, TaskRecord
from ...shared.paths import task_dir as resolve_task_dir
from ..config.loader import SisyphusConfig
from .task_repository import (
    list_task_records,
    load_task_record,
    save_task_record,
    update_task_record,
)


class FileTaskRecordAdapter:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._repo_root = repo_root
        self._config = config

    def load(self, task_id: str) -> TaskRecord:
        task, _ = load_task_record(self._repo_root, self._config.task_dir, task_id)
        return task

    def save(self, task: TaskRecord) -> None:
        self._save(task, mirror_support=True)

    def save_promotion_state(self, task: TaskRecord) -> None:
        self._save(task, mirror_support=False)

    def _save(self, task: TaskRecord, *, mirror_support: bool) -> None:
        task_id = str(task.get("id") or "")
        if not task_id:
            raise ValueError("task record requires an id")
        task_file = resolve_task_dir(
            self._repo_root,
            self._config.task_dir,
            task_id,
        ) / "task.json"
        save_task_record(
            task_file=task_file,
            task=task,
            mirror_support=mirror_support,
        )

    def update(self, task_id: str, mutator: TaskMutator) -> TaskRecord:
        task, _ = update_task_record(
            self._repo_root,
            self._config.task_dir,
            task_id,
            mutator,
        )
        return task

    def list(self) -> tuple[TaskRecord, ...]:
        return tuple(list_task_records(self._repo_root, self._config.task_dir))


__all__ = ["FileTaskRecordAdapter"]
