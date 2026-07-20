from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .workflow import TaskRecord, TaskRecordPort


class PromotionTaskPort(TaskRecordPort, Protocol):
    def list(self) -> tuple[TaskRecord, ...]: ...


class VersionControlPort(Protocol):
    def workspace_exists(self, workspace: str) -> bool: ...

    def stage_all(self, workspace: str) -> None: ...

    def has_staged_changes(self, workspace: str) -> bool: ...

    def commit(self, workspace: str, message: str) -> str: ...

    def push(self, workspace: str, remote: str, branch: str) -> None: ...

    def push_revision(
        self,
        workspace: str,
        remote: str,
        revision: str,
        branch: str,
    ) -> None: ...

    def remote_url(self, workspace: str, remote: str) -> str | None: ...


@dataclass(frozen=True, slots=True)
class PullRequestSpec:
    workspace: str
    repo_full_name: str | None
    base_branch: str
    head_branch: str
    title: str
    body: str
    draft: bool


class PullRequestPort(Protocol):
    def find_open(self, spec: PullRequestSpec) -> str | None: ...

    def create(self, spec: PullRequestSpec) -> str: ...


class ReopenedTaskPort(Protocol):
    def publish(
        self,
        *,
        task_id: str,
        reason: str,
        workflow_phase: str,
        previous_verify_status: str,
    ) -> None: ...


__all__ = [
    "PromotionTaskPort",
    "PullRequestPort",
    "PullRequestSpec",
    "ReopenedTaskPort",
    "VersionControlPort",
]
