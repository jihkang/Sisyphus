from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class QueueConversationCommand:
    message: str
    title: str | None = None
    task_type: str = "feature"
    slug: str | None = None
    instruction: str | None = None
    agent_id: str = "worker-1"
    role: str = "worker"
    provider: str = "codex"
    owned_paths: tuple[str, ...] = ()
    provider_args: tuple[str, ...] = ()
    source_context: Mapping[str, object] | None = None
    adopt_current_changes: bool = False
    adopt_paths: tuple[str, ...] = ()
    auto_run: bool = True


@dataclass(frozen=True, slots=True)
class QueuePullRequestMergedCommand:
    pr_number: int
    title: str
    task_id: str | None = None
    branch: str | None = None
    repo_full_name: str | None = None
    url: str | None = None
    base_branch: str | None = None
    head_branch: str | None = None
    head_sha: str | None = None
    merge_commit_sha: str | None = None
    merged_at: str | None = None
    merged_by: str | None = None
    merge_method: str | None = None
    additions: int | None = None
    deletions: int | None = None
    changed_files: tuple[Mapping[str, object], ...] = ()


__all__ = ["QueueConversationCommand", "QueuePullRequestMergedCommand"]
