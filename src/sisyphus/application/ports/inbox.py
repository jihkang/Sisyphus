from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeAlias

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


__all__ = [
    "InboxEventHandler",
    "InboxEventLogPort",
    "InboxEventParser",
    "InboxEventProcessor",
    "InboxRecord",
    "InboxRepositoryPort",
    "Sleeper",
    "WorkflowCycle",
]
