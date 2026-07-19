from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..results.inbox_handlers import AdoptedChanges, PromotionMergeReceipt

from ..commands.promotion import RecordMergedPullRequestCommand
from .workflow import TaskRecord


class ConversationDocumentPort(Protocol):
    def materialize(
        self,
        task: TaskRecord,
        *,
        title: str,
        message: str,
        requested_slug: str,
        parent_task_id: str | None,
    ) -> None: ...

    def append_log_note(self, task: TaskRecord, note: str) -> None: ...


class ChangeAdoptionPort(Protocol):
    def apply(
        self,
        *,
        worktree_root: Path,
        requested_paths: tuple[str, ...],
    ) -> AdoptedChanges: ...


class TaskExecutionGatePort(Protocol):
    def enforce_plan_approved(
        self,
        task_id: str,
        *,
        action: str,
    ) -> tuple[bool, TaskRecord]: ...

    def enforce_spec_frozen(
        self,
        task_id: str,
        *,
        action: str,
    ) -> tuple[bool, TaskRecord]: ...


class ConversationAgentPort(Protocol):
    def run(
        self,
        *,
        provider: str,
        task_id: str,
        agent_id: str,
        role: str,
        instruction: str | None,
        owned_paths: tuple[str, ...],
        provider_args: tuple[str, ...],
    ) -> int: ...


class PromotionMergePort(Protocol):
    def record(self, command: RecordMergedPullRequestCommand) -> PromotionMergeReceipt: ...


__all__ = [
    "ChangeAdoptionPort",
    "ConversationAgentPort",
    "ConversationDocumentPort",
    "PromotionMergePort",
    "TaskExecutionGatePort",
]
