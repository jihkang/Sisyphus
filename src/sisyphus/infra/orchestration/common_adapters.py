from __future__ import annotations

from pathlib import Path

from ...application.ports.workflow import TaskMutator, TaskRecord, WorkflowEvent
from ...bus import build_event_publisher
from ...config import SisyphusConfig
from ...events import new_event_envelope
from ...metrics import publish_manual_intervention_required, publish_reopened_after_verify
from ...shared.paths import task_dir as resolve_task_dir
from ..persistence.task_repository import (
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

    def list(self) -> tuple[TaskRecord, ...]:
        return tuple(list_task_records(self._repo_root, self._config.task_dir))


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


class EventPublisherAdapter:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._publisher = build_event_publisher(repo_root, config)

    def publish(self, event: WorkflowEvent) -> None:
        self._publisher.publish(
            new_event_envelope(
                event.event_type,
                source=event.source,
                data=event.data,
            )
        )


class ReopenedTaskAdapter:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._repo_root = repo_root
        self._config = config

    def publish(
        self,
        *,
        task_id: str,
        reason: str,
        workflow_phase: str,
        previous_verify_status: str,
    ) -> None:
        publish_reopened_after_verify(
            self._repo_root,
            self._config,
            task_id=task_id,
            reason=reason,
            workflow_phase=workflow_phase,
            previous_verify_status=previous_verify_status,
        )


__all__ = [
    "EventPublisherAdapter",
    "FileTaskRecordAdapter",
    "ManualInterventionAdapter",
    "ReopenedTaskAdapter",
]
