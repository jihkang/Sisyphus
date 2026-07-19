from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .application.results.repository_requests import (
    MergeRecordResult,
    QueuedConversation,
    QueuedPullRequestMerge,
    TaskRequestResult,
)
from .composition.repository_requests import (
    build_repository_request_service,
    get_task as get_task_record,
    list_tasks as list_task_records,
    queue_conversation as queue_repository_conversation,
    queue_pull_request_merged as queue_repository_pull_request_merged,
    record_merged_pull_request as record_repository_pull_request_merge,
    request_task as request_repository_task,
)
from .config import SisyphusConfig, load_config
from .promotion import execute_promotion as run_promotion_execution


@dataclass(slots=True)
class RepositoryPromotionExecutionResult:
    task_id: str | None
    status: str | None
    branch: str | None
    base_branch: str | None
    head_branch: str | None
    commit_sha: str | None
    pr_number: int | None
    pr_url: str | None
    receipt_path: Path | None
    error: str | None

    @property
    def ok(self) -> bool:
        return self.error is None and self.task_id is not None


def queue_conversation(
    repo_root: Path,
    *,
    message: str,
    title: str | None = None,
    task_type: str = "feature",
    slug: str | None = None,
    instruction: str | None = None,
    agent_id: str = "worker-1",
    role: str = "worker",
    provider: str = "codex",
    owned_paths: list[str] | None = None,
    provider_args: list[str] | None = None,
    source_context: dict[str, object] | None = None,
    adopt_current_changes: bool = False,
    adopt_paths: list[str] | None = None,
    auto_run: bool = True,
) -> QueuedConversation:
    return queue_repository_conversation(
        repo_root,
        message=message,
        title=title,
        task_type=task_type,
        slug=slug,
        instruction=instruction,
        agent_id=agent_id,
        role=role,
        provider=provider,
        owned_paths=owned_paths,
        provider_args=provider_args,
        source_context=source_context,
        adopt_current_changes=adopt_current_changes,
        adopt_paths=adopt_paths,
        auto_run=auto_run,
    )


def request_task(
    repo_root: Path,
    *,
    config: SisyphusConfig | None = None,
    message: str,
    title: str | None = None,
    task_type: str = "feature",
    slug: str | None = None,
    instruction: str | None = None,
    agent_id: str = "worker-1",
    role: str = "worker",
    provider: str = "codex",
    owned_paths: list[str] | None = None,
    provider_args: list[str] | None = None,
    source_context: dict[str, object] | None = None,
    adopt_current_changes: bool = False,
    adopt_paths: list[str] | None = None,
    auto_run: bool = True,
) -> TaskRequestResult:
    return request_repository_task(
        repo_root,
        config=config,
        message=message,
        title=title,
        task_type=task_type,
        slug=slug,
        instruction=instruction,
        agent_id=agent_id,
        role=role,
        provider=provider,
        owned_paths=owned_paths,
        provider_args=provider_args,
        source_context=source_context,
        adopt_current_changes=adopt_current_changes,
        adopt_paths=adopt_paths,
        auto_run=auto_run,
    )


def queue_pull_request_merged(
    repo_root: Path,
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
) -> QueuedPullRequestMerge:
    return queue_repository_pull_request_merged(
        repo_root,
        task_id=task_id,
        branch=branch,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        title=title,
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
        changed_files=changed_files,
    )


def record_merged_pull_request(
    repo_root: Path,
    *,
    config: SisyphusConfig | None = None,
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
) -> MergeRecordResult:
    return record_repository_pull_request_merge(
        repo_root,
        config=config,
        task_id=task_id,
        branch=branch,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        title=title,
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
        changed_files=changed_files,
    )


def execute_promotion(
    repo_root: Path,
    *,
    config: SisyphusConfig | None = None,
    task_id: str,
    remote_name: str = "origin",
    repo_full_name: str | None = None,
    title: str | None = None,
    body: str | None = None,
    commit_message: str | None = None,
    base_branch: str | None = None,
    head_branch: str | None = None,
    draft: bool = True,
) -> RepositoryPromotionExecutionResult:
    effective_config = config or load_config(repo_root)
    try:
        outcome = run_promotion_execution(
            repo_root=repo_root,
            config=effective_config,
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
    except Exception as exc:
        return RepositoryPromotionExecutionResult(
            task_id=task_id,
            status=None,
            branch=None,
            base_branch=None,
            head_branch=None,
            commit_sha=None,
            pr_number=None,
            pr_url=None,
            receipt_path=None,
            error=str(exc),
        )

    return RepositoryPromotionExecutionResult(
        task_id=outcome.task_id,
        status=outcome.status,
        branch=outcome.branch,
        base_branch=outcome.base_branch,
        head_branch=outcome.head_branch,
        commit_sha=outcome.commit_sha,
        pr_number=outcome.pr_number,
        pr_url=outcome.pr_url,
        receipt_path=outcome.receipt_path,
        error=None,
    )


def run_until_stable(repo_root: Path, *, config: SisyphusConfig | None = None) -> int:
    return build_repository_request_service(repo_root, config).run_until_stable()


def get_task(repo_root: Path, task_id: str, *, config: SisyphusConfig | None = None) -> dict:
    return get_task_record(repo_root, task_id, config=config)


def list_tasks(repo_root: Path, *, config: SisyphusConfig | None = None) -> list[dict]:
    return list_task_records(repo_root, config=config)


PromotionExecutionResult = RepositoryPromotionExecutionResult
