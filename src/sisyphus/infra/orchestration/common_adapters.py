from __future__ import annotations

from pathlib import Path

from ...application.ports.workflow import TaskMutator, TaskRecord
from ...config import SisyphusConfig
from ...metrics import publish_manual_intervention_required
from ...shared.paths import task_dir as resolve_task_dir
from ..persistence.task_repository import load_task_record, save_task_record, update_task_record


class FileTaskRecordAdapter:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._repo_root = repo_root
        self._config = config

    def load(self, task_id: str) -> TaskRecord:
        task, _ = load_task_record(self._repo_root, self._config.task_dir, task_id)
        return task

    def save(self, task: TaskRecord) -> None:
        task_id = str(task.get("id") or "")
        if not task_id:
            raise ValueError("task record requires an id")
        task_file = resolve_task_dir(self._repo_root, self._config.task_dir, task_id) / "task.json"
        save_task_record(task_file=task_file, task=task)

    def update(self, task_id: str, mutator: TaskMutator) -> TaskRecord:
        task, _ = update_task_record(
            self._repo_root,
            self._config.task_dir,
            task_id,
            mutator,
        )
        return task


class ManualInterventionAdapter:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._repo_root = repo_root
        self._config = config

    def required(
        self,
        *,
        task_id: str,
        reason: str,
        workflow_phase: str,
        status: str,
        detail: str,
    ) -> None:
        publish_manual_intervention_required(
            self._repo_root,
            self._config,
            task_id=task_id,
            reason=reason,
            workflow_phase=workflow_phase,
            status=status,
            detail=detail,
        )


__all__ = ["FileTaskRecordAdapter", "ManualInterventionAdapter"]
