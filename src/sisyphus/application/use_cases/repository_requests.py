from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..commands.inbox import QueueConversationCommand, QueuePullRequestMergedCommand
from ..ports.inbox import InboxProcessingPort, InboxQueuePort, WorkflowCycle
from ..ports.workflow import TaskRecordPort
from ..results.repository_requests import (
    MergeRecordResult,
    QueuedConversation,
    QueuedPullRequestMerge,
    TaskRequestResult,
)


EventPathResolver = Callable[[str, str], Path]


@dataclass(slots=True)
class RepositoryRequestService:
    queue: InboxQueuePort
    processing: InboxProcessingPort
    tasks: TaskRecordPort
    workflow_cycle: WorkflowCycle
    resolve_event_path: EventPathResolver

    def queue_conversation(
        self,
        command: QueueConversationCommand,
    ) -> QueuedConversation:
        event, event_path = self.queue.queue_conversation(command)
        return QueuedConversation(event=event, event_path=event_path)

    def request_task(self, command: QueueConversationCommand) -> TaskRequestResult:
        queued = self.queue_conversation(command)
        processed_event = self.processing.process(queued.event_path)
        orchestrated = 0
        if processed_event.get("status") == "processed" and command.auto_run:
            orchestrated = self.run_until_stable()

        result = processed_event.get("result")
        task_id_value = result.get("task_id") if isinstance(result, dict) else None
        task_id = str(task_id_value) if task_id_value else None
        task = self.tasks.load(task_id) if task_id else None
        status = str(processed_event.get("status"))
        error_value = processed_event.get("error")
        return TaskRequestResult(
            event_id=queued.event_id,
            event_status=status,
            event_path=self.resolve_event_path(queued.event_id, status),
            task_id=task_id,
            task=task,
            orchestrated=orchestrated,
            error=str(error_value) if error_value is not None else None,
            processed_event=processed_event,
        )

    def queue_pull_request_merged(
        self,
        command: QueuePullRequestMergedCommand,
    ) -> QueuedPullRequestMerge:
        event, event_path = self.queue.queue_pull_request_merged(command)
        return QueuedPullRequestMerge(event=event, event_path=event_path)

    def record_merged_pull_request(
        self,
        command: QueuePullRequestMergedCommand,
    ) -> MergeRecordResult:
        queued = self.queue_pull_request_merged(command)
        processed_event = self.processing.process(queued.event_path)
        result_value = processed_event.get("result")
        result = result_value if isinstance(result_value, dict) else {}
        status = str(processed_event.get("status"))
        error_value = processed_event.get("error")
        task_id_value = result.get("task_id")
        pr_number_value = result.get("pr_number")
        return MergeRecordResult(
            event_id=queued.event_id,
            event_status=status,
            event_path=self.resolve_event_path(queued.event_id, status),
            task_id=str(task_id_value) if task_id_value else None,
            pr_number=int(pr_number_value) if pr_number_value is not None else None,
            receipt_path=Path(str(result["receipt_path"])) if result.get("receipt_path") else None,
            changeset_path=(
                Path(str(result["changeset_path"])) if result.get("changeset_path") else None
            ),
            close_attempted=bool(result.get("close_attempted", False)),
            closed=bool(result.get("closed", False)),
            close_status=(
                str(result["close_status"]) if result.get("close_status") is not None else None
            ),
            close_gate_codes=_string_list(result.get("close_gate_codes")),
            child_retargeted_task_ids=_string_list(
                result.get("child_retargeted_task_ids")
            ),
            error=str(error_value) if error_value is not None else None,
            processed_event=processed_event,
        )

    def run_until_stable(self) -> int:
        orchestrated = 0
        while True:
            progressed = self.workflow_cycle()
            if progressed == 0:
                return orchestrated
            orchestrated += progressed


@dataclass(frozen=True, slots=True)
class TaskRecordQueryService:
    tasks: TaskRecordPort

    def get(self, task_id: str) -> dict[str, object]:
        return self.tasks.load(task_id)

    def list(self) -> list[dict[str, object]]:
        return list(self.tasks.list())


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


__all__ = ["RepositoryRequestService", "TaskRecordQueryService"]
