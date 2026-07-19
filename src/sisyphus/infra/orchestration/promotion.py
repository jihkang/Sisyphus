from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from ...application.commands.promotion import ExecutePromotionCommand, RecordMergedPullRequestCommand
from ...application.use_cases.promotion import (
    DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH,
    PromotionExecutionError,
)
from ...composition.promotion import build_promotion_service
from ...config import SisyphusConfig
from ...domain.promotion import PromotionBaseResolution
from ...gitops import GitOperationError
from ...shared.paths import contained_path, task_dir as resolve_task_dir


@dataclass(slots=True)
class MergeReceiptOutcome:
    task_id: str
    branch: str | None
    pr_number: int
    title: str
    recorded_at: str
    receipt_path: Path
    changeset_path: Path
    close_attempted: bool
    closed: bool
    close_status: str | None
    close_gate_codes: tuple[str, ...]
    child_retargeted_task_ids: tuple[str, ...]


@dataclass(slots=True)
class RepositoryPromotionExecution:
    task_id: str
    branch: str
    base_branch: str
    head_branch: str
    status: str
    commit_sha: str
    pr_number: int | None
    pr_url: str | None
    receipt_path: Path


def execute_promotion(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    task_id: str,
    remote_name: str = "origin",
    repo_full_name: str | None = None,
    title: str | None = None,
    body: str | None = None,
    commit_message: str | None = None,
    base_branch: str | None = None,
    head_branch: str | None = None,
    draft: bool = True,
) -> RepositoryPromotionExecution:
    try:
        result = build_promotion_service(
            repo_root,
            config,
            gh_runner=_run_gh,
        ).execute(
            ExecutePromotionCommand(
                task_id=task_id,
                remote_name=remote_name,
                repo_full_name=repo_full_name,
                title=title,
                body=body,
                commit_message=commit_message,
                base_branch=base_branch,
                head_branch=head_branch,
                draft=draft,
            )
        )
    except PromotionExecutionError as error:
        raise GitOperationError(str(error)) from error
    return RepositoryPromotionExecution(
        task_id=result.task_id,
        branch=result.branch,
        base_branch=result.base_branch,
        head_branch=result.head_branch,
        status=result.status,
        commit_sha=result.commit_sha,
        pr_number=result.pr_number,
        pr_url=result.pr_url,
        receipt_path=_artifact_path(repo_root, config, result.task_id, result.receipt.relative_path),
    )


def resolve_promotion_base(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task: dict,
    explicit_base_branch: str | None = None,
) -> PromotionBaseResolution:
    return build_promotion_service(repo_root, config, gh_runner=_run_gh).resolve_base(
        task,
        explicit_base_branch=explicit_base_branch,
    )


def mark_stacked_children_for_retarget(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    parent_task: dict,
    triggered_at: str,
) -> tuple[str, ...]:
    return build_promotion_service(
        repo_root,
        config,
        gh_runner=_run_gh,
    ).mark_stacked_children_for_retarget(parent_task, triggered_at=triggered_at)


def record_merged_pull_request(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    pr_number: int,
    title: str,
    task_id: str | None = None,
    branch: str | None = None,
    repo_full_name: str | None = None,
    url: str | None = None,
    base_branch: str | None = None,
    head_branch: str | None = None,
    head_sha: str | None = None,
    merge_commit_sha: str | None = None,
    merged_at: str | None = None,
    merged_by: str | None = None,
    merge_method: str | None = None,
    additions: int | None = None,
    deletions: int | None = None,
    changed_files: list[dict[str, object]] | None = None,
) -> MergeReceiptOutcome:
    result = build_promotion_service(repo_root, config, gh_runner=_run_gh).record_merged(
        RecordMergedPullRequestCommand(
            pr_number=pr_number,
            title=title,
            task_id=task_id,
            branch=branch,
            repo_full_name=repo_full_name,
            url=url,
            base_branch=base_branch,
            head_branch=head_branch,
            head_sha=head_sha,
            merge_commit_sha=merge_commit_sha,
            merged_at=merged_at,
            merged_by=merged_by,
            merge_method=merge_method,
            additions=additions,
            deletions=deletions,
            changed_files=tuple(changed_files or ()),
        )
    )
    return MergeReceiptOutcome(
        task_id=result.task_id,
        branch=result.branch,
        pr_number=result.pr_number,
        title=result.title,
        recorded_at=result.recorded_at,
        receipt_path=_artifact_path(repo_root, config, result.task_id, result.receipt.relative_path),
        changeset_path=_artifact_path(repo_root, config, result.task_id, result.changeset.relative_path),
        close_attempted=result.close_attempted,
        closed=result.closed,
        close_status=result.close_status,
        close_gate_codes=result.close_gate_codes,
        child_retargeted_task_ids=result.child_retargeted_task_ids,
    )


def _run_gh(
    repo_root: Path,
    args: list[str],
    *,
    error_prefix: str,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["gh", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return completed
    message = (completed.stderr or completed.stdout or "").strip() or "gh command failed"
    raise GitOperationError(f"{error_prefix}: {message}")


def _artifact_path(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    relative_path: str,
) -> Path:
    directory = resolve_task_dir(repo_root, config.task_dir, task_id)
    return contained_path(directory, relative_path, require_relative=True)


PromotionExecutionOutcome = RepositoryPromotionExecution


__all__ = [
    "DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH",
    "MergeReceiptOutcome",
    "PromotionBaseResolution",
    "PromotionExecutionOutcome",
    "RepositoryPromotionExecution",
    "execute_promotion",
    "mark_stacked_children_for_retarget",
    "record_merged_pull_request",
    "resolve_promotion_base",
]
