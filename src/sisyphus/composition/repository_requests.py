from __future__ import annotations

from pathlib import Path

from ..application.commands.inbox import QueueConversationCommand, QueuePullRequestMergedCommand
from ..application.results.repository_requests import (
    MergeRecordResult,
    QueuedConversation,
    QueuedPullRequestMerge,
    TaskRequestResult,
)
from ..application.use_cases.repository_requests import (
    RepositoryRequestService,
    TaskRecordQueryService,
)
from ..infra.config.loader import SisyphusConfig, load_config
from ..infra.daemon import new_event_id
from ..infra.orchestration.workflow import run_workflow_cycle
from ..infra.persistence.task_records import FileTaskRecordAdapter
from ..shared.paths import inbox_failed_dir, inbox_processed_dir
from .daemon import build_repository_inbox_processing_service
from .inbox import build_inbox_queue_service


def build_repository_request_service(
    repo_root: Path,
    config: SisyphusConfig | None = None,
) -> RepositoryRequestService:
    effective_config = config or load_config(repo_root)
    return RepositoryRequestService(
        queue=build_inbox_queue_service(
            repo_root,
            effective_config,
            new_event_id=new_event_id,
        ),
        processing=build_repository_inbox_processing_service(repo_root, effective_config),
        tasks=FileTaskRecordAdapter(repo_root, effective_config),
        workflow_cycle=lambda: run_workflow_cycle(repo_root, effective_config),
        resolve_event_path=lambda event_id, status: _processed_event_path(
            repo_root,
            event_id,
            status,
        ),
    )


def build_task_record_query_service(
    repo_root: Path,
    config: SisyphusConfig | None = None,
) -> TaskRecordQueryService:
    effective_config = config or load_config(repo_root)
    return TaskRecordQueryService(FileTaskRecordAdapter(repo_root, effective_config))


def queue_conversation(
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
) -> QueuedConversation:
    return build_repository_request_service(repo_root, config).queue_conversation(
        QueueConversationCommand(
            message=message,
            title=title,
            task_type=task_type,
            slug=slug,
            instruction=instruction,
            agent_id=agent_id,
            role=role,
            provider=provider,
            owned_paths=tuple(owned_paths or ()),
            provider_args=tuple(provider_args or ()),
            source_context=source_context,
            adopt_current_changes=adopt_current_changes,
            adopt_paths=tuple(adopt_paths or ()),
            auto_run=auto_run,
        )
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
    return build_repository_request_service(repo_root, config).request_task(
        QueueConversationCommand(
            message=message,
            title=title,
            task_type=task_type,
            slug=slug,
            instruction=instruction,
            agent_id=agent_id,
            role=role,
            provider=provider,
            owned_paths=tuple(owned_paths or ()),
            provider_args=tuple(provider_args or ()),
            source_context=source_context,
            adopt_current_changes=adopt_current_changes,
            adopt_paths=tuple(adopt_paths or ()),
            auto_run=auto_run,
        )
    )


def queue_pull_request_merged(
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
) -> QueuedPullRequestMerge:
    return build_repository_request_service(repo_root, config).queue_pull_request_merged(
        QueuePullRequestMergedCommand(
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


def record_merged_pull_request(
    repo_root: Path,
    *,
    config: SisyphusConfig | None = None,
    **kwargs: object,
) -> MergeRecordResult:
    command = QueuePullRequestMergedCommand(
        pr_number=int(kwargs["pr_number"]),
        title=str(kwargs["title"]),
        task_id=_optional_text(kwargs.get("task_id")),
        branch=_optional_text(kwargs.get("branch")),
        repo_full_name=_optional_text(kwargs.get("repo_full_name")),
        url=_optional_text(kwargs.get("url")),
        base_branch=_optional_text(kwargs.get("base_branch")),
        head_branch=_optional_text(kwargs.get("head_branch")),
        head_sha=_optional_text(kwargs.get("head_sha")),
        merge_commit_sha=_optional_text(kwargs.get("merge_commit_sha")),
        merged_at=_optional_text(kwargs.get("merged_at")),
        merged_by=_optional_text(kwargs.get("merged_by")),
        merge_method=_optional_text(kwargs.get("merge_method")),
        additions=_optional_int(kwargs.get("additions")),
        deletions=_optional_int(kwargs.get("deletions")),
        changed_files=tuple(kwargs.get("changed_files") or ()),
    )
    return build_repository_request_service(repo_root, config).record_merged_pull_request(command)


def get_task(
    repo_root: Path,
    task_id: str,
    *,
    config: SisyphusConfig | None = None,
) -> dict[str, object]:
    return build_task_record_query_service(repo_root, config).get(task_id)


def list_tasks(
    repo_root: Path,
    *,
    config: SisyphusConfig | None = None,
) -> list[dict[str, object]]:
    return build_task_record_query_service(repo_root, config).list()


def _processed_event_path(repo_root: Path, event_id: str, status: str) -> Path:
    filename = f"{event_id}.json"
    return (
        inbox_processed_dir(repo_root) / filename
        if status == "processed"
        else inbox_failed_dir(repo_root) / filename
        if status == "failed"
        else inbox_processed_dir(repo_root) / filename
    )


def _optional_text(value: object) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: object) -> int | None:
    return int(value) if value is not None else None


__all__ = [
    "build_repository_request_service",
    "build_task_record_query_service",
    "get_task",
    "list_tasks",
    "queue_conversation",
    "queue_pull_request_merged",
    "record_merged_pull_request",
    "request_task",
]
