from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..ports.workflow import TaskRecord


@dataclass(slots=True)
class QueuedConversation:
    event: dict[str, object]
    event_path: Path

    @property
    def event_id(self) -> str:
        return str(self.event["id"])


@dataclass(slots=True)
class TaskRequestResult:
    event_id: str
    event_status: str
    event_path: Path
    task_id: str | None
    task: TaskRecord | None
    orchestrated: int
    error: str | None
    processed_event: dict[str, object]

    @property
    def ok(self) -> bool:
        return self.error is None and self.event_status == "processed"


@dataclass(slots=True)
class QueuedPullRequestMerge:
    event: dict[str, object]
    event_path: Path

    @property
    def event_id(self) -> str:
        return str(self.event["id"])


@dataclass(slots=True)
class MergeRecordResult:
    event_id: str
    event_status: str
    event_path: Path
    task_id: str | None
    pr_number: int | None
    receipt_path: Path | None
    changeset_path: Path | None
    close_attempted: bool
    closed: bool
    close_status: str | None
    close_gate_codes: list[str]
    child_retargeted_task_ids: list[str]
    error: str | None
    processed_event: dict[str, object]

    @property
    def ok(self) -> bool:
        return self.error is None and self.event_status == "processed"


__all__ = [
    "MergeRecordResult",
    "QueuedConversation",
    "QueuedPullRequestMerge",
    "TaskRequestResult",
]
