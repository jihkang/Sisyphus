from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import re

from ...domain.inbox import InboxValidationError
from ...domain.task.documents import single_line
from ..commands.inbox import QueueConversationCommand, QueuePullRequestMergedCommand
from ..ports.clock import ClockPort
from ..ports.inbox import (
    InboxEventLogPort,
    InboxEventParser,
    InboxRecord,
    InboxRepositoryPort,
)
from ..ports.workflow import EventPublisherPort, WorkflowEvent


class DaemonError(RuntimeError):
    """Raised when inbox processing cannot continue safely."""


@dataclass(slots=True)
class InboxQueueService:
    inbox: InboxRepositoryPort
    parse_event: InboxEventParser
    event_log: InboxEventLogPort
    events: EventPublisherPort
    clock: ClockPort
    new_event_id: Callable[[], str]

    def queue_conversation(
        self,
        command: QueueConversationCommand,
    ) -> tuple[InboxRecord, Path]:
        event_id = self.new_event_id()
        event = self._validated(
            {
                "id": event_id,
                "event_type": "conversation",
                "status": "queued",
                "created_at": self.clock.now(),
                "updated_at": self.clock.now(),
                "payload": {
                    "title": command.title if command.title is not None else "",
                    "message": command.message,
                    "task_type": command.task_type,
                    "slug": command.slug if command.slug is not None else "",
                    "instruction": command.instruction,
                    "agent_id": command.agent_id,
                    "role": command.role,
                    "provider": command.provider,
                    "owned_paths": list(command.owned_paths),
                    "provider_args": list(command.provider_args),
                    "source_context": dict(command.source_context or {}),
                    "adopt_current_changes": command.adopt_current_changes,
                    "adopt_paths": list(command.adopt_paths),
                    "auto_run": command.auto_run,
                },
                "result": None,
                "error": None,
            }
        )
        payload = dict(event["payload"])
        payload["title"] = payload["title"] or _title_from_message(str(payload["message"]))
        payload["slug"] = payload["slug"] or _slugify(
            str(payload["title"]),
            fallback=f"conversation-task-{event_id[-4:]}",
        )
        event["payload"] = payload
        event_path = self.inbox.enqueue(event)
        self.event_log.append(
            {
                "timestamp": self.clock.now(),
                "event_id": event_id,
                "event_type": "conversation",
                "status": "queued",
                "message": "conversation event queued",
            }
        )
        self.events.publish(
            WorkflowEvent(
                event_type="conversation.queued",
                source={"module": "daemon"},
                data={
                    "event_id": event_id,
                    "task_type": command.task_type,
                    "slug": payload["slug"],
                },
            )
        )
        return event, event_path

    def queue_pull_request_merged(
        self,
        command: QueuePullRequestMergedCommand,
    ) -> tuple[InboxRecord, Path]:
        event_id = self.new_event_id()
        event = self._validated(
            {
                "id": event_id,
                "event_type": "pull_request_merged",
                "status": "queued",
                "created_at": self.clock.now(),
                "updated_at": self.clock.now(),
                "payload": {
                    "task_id": command.task_id,
                    "branch": command.branch,
                    "repo_full_name": command.repo_full_name,
                    "pr_number": command.pr_number,
                    "title": command.title,
                    "url": command.url,
                    "base_branch": command.base_branch,
                    "head_branch": command.head_branch,
                    "head_sha": command.head_sha,
                    "merge_commit_sha": command.merge_commit_sha,
                    "merged_at": command.merged_at,
                    "merged_by": command.merged_by,
                    "merge_method": command.merge_method,
                    "additions": command.additions,
                    "deletions": command.deletions,
                    "changed_files": [dict(item) for item in command.changed_files],
                },
                "result": None,
                "error": None,
            }
        )
        payload = dict(event["payload"])
        event_path = self.inbox.enqueue(event)
        self.event_log.append(
            {
                "timestamp": self.clock.now(),
                "event_id": event_id,
                "event_type": "pull_request_merged",
                "status": "queued",
                "message": (
                    "pull request merge event queued for pr "
                    f"#{command.pr_number}"
                ),
            }
        )
        self.events.publish(
            WorkflowEvent(
                event_type="pull_request.merged.queued",
                source={"module": "daemon"},
                data={
                    "event_id": event_id,
                    "task_id": payload.get("task_id"),
                    "branch": payload.get("branch"),
                    "pr_number": command.pr_number,
                },
            )
        )
        return event, event_path

    def _validated(self, raw_event: InboxRecord) -> InboxRecord:
        try:
            return self.parse_event(raw_event)
        except InboxValidationError as exc:
            raise DaemonError(str(exc)) from None


def _slugify(value: str, *, fallback: str = "conversation-task") -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized[:48] or fallback


def _title_from_message(message: str) -> str:
    line = single_line(message)
    return line[:72] or "Conversation Task"


__all__ = [
    "DaemonError",
    "InboxQueueService",
]
