from __future__ import annotations

from pathlib import Path

from ...application.ports.workflow import WorkflowEvent
from ...events import new_event_envelope
from ...metrics import publish_manual_intervention_required, publish_reopened_after_verify
from ..config.loader import SisyphusConfig
from ..events import build_event_publisher
from ..persistence.task_records import FileTaskRecordAdapter


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
