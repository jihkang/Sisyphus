from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeAlias

from ..commands.inbox import QueueConversationCommand, QueuePullRequestMergedCommand

if TYPE_CHECKING:
    from ..results.inbox import DaemonStats


InboxRecord: TypeAlias = dict[str, object]
InboxEventParser: TypeAlias = Callable[[object], InboxRecord]
InboxEventHandler: TypeAlias = Callable[[InboxRecord], dict[str, object]]
InboxEventProcessor: TypeAlias = Callable[[Path, "DaemonStats"], InboxRecord]
WorkflowCycle: TypeAlias = Callable[[], int]
Sleeper: TypeAlias = Callable[[float], None]


class InboxRepositoryPort(Protocol):
    def enqueue(self, event: InboxRecord) -> Path: ...

    def list_processable(self) -> list[Path]: ...

    def claim(self, event_path: Path) -> Path: ...

    def read(self, event_path: Path) -> object: ...

    def update(self, event_path: Path, event: InboxRecord) -> None: ...

    def complete(self, event_path: Path, event: InboxRecord) -> Path: ...

    def fail(self, event_path: Path, event: InboxRecord) -> Path: ...


class InboxEventLogPort(Protocol):
    def append(self, entry: Mapping[str, object]) -> None: ...


class InboxQueuePort(Protocol):
    def queue_conversation(
        self,
        command: QueueConversationCommand,
    ) -> tuple[InboxRecord, Path]: ...

    def queue_pull_request_merged(
        self,
        command: QueuePullRequestMergedCommand,
    ) -> tuple[InboxRecord, Path]: ...


class InboxProcessingPort(Protocol):
    def process(
        self,
        event_path: Path,
        *,
        stats: "DaemonStats | None" = None,
    ) -> InboxRecord: ...


__all__ = [
    "InboxEventHandler",
    "InboxEventLogPort",
    "InboxEventParser",
    "InboxEventProcessor",
    "InboxRecord",
    "InboxProcessingPort",
    "InboxQueuePort",
    "InboxRepositoryPort",
    "Sleeper",
    "WorkflowCycle",
]
