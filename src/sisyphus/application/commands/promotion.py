from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutePromotionCommand:
    task_id: str
    remote_name: str = "origin"
    repo_full_name: str | None = None
    title: str | None = None
    body: str | None = None
    commit_message: str | None = None
    base_branch: str | None = None
    head_branch: str | None = None
    draft: bool = True


@dataclass(frozen=True, slots=True)
class RecordMergedPullRequestCommand:
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
    changed_files: tuple[dict[str, object], ...] = ()


__all__ = ["ExecutePromotionCommand", "RecordMergedPullRequestCommand"]
