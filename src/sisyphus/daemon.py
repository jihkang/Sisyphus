from __future__ import annotations

from pathlib import Path

from .application.commands.inbox import (
    QueueConversationCommand,
    QueuePullRequestMergedCommand,
)
from .application.results.inbox import DaemonStats
from .application.use_cases.inbox import DaemonError
from .composition.inbox import (
    build_daemon_loop_service,
    build_inbox_processing_service,
    build_inbox_queue_service,
)
from .composition.inbox_handlers import (
    build_callable_task_execution_gate,
    build_conversation_event_service,
    build_pull_request_merged_event_service,
)
from .config import SisyphusConfig, load_config
from .domain.task.documents import (
    render_brief as _render_brief,
    render_feature_plan as _render_feature_plan,
    render_issue_fix_plan as _render_issue_fix_plan,
    render_issue_repro as _render_issue_repro,
)
from .infra.daemon import is_internal_sisyphus_path, new_event_id
from .planning import enforce_plan_approved, enforce_spec_frozen
from .provider_wrapper import run_provider_wrapper
from .workflow import run_workflow_cycle


def queue_conversation_event(
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
) -> tuple[dict, Path]:
    return build_inbox_queue_service(
        repo_root,
        load_config(repo_root),
        new_event_id=_new_event_id,
    ).queue_conversation(
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


def queue_pull_request_merged_event(
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
) -> tuple[dict, Path]:
    return build_inbox_queue_service(
        repo_root,
        load_config(repo_root),
        new_event_id=_new_event_id,
    ).queue_pull_request_merged(
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


def run_daemon(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    once: bool,
    poll_interval_seconds: int,
    max_events: int | None = None,
) -> DaemonStats:
    return build_daemon_loop_service(
        repo_root,
        process_event=lambda event_path, stats: process_inbox_event(
            repo_root=repo_root,
            config=config,
            event_path=event_path,
            stats=stats,
        ),
        workflow_cycle=lambda: run_workflow_cycle(repo_root=repo_root, config=config),
    ).run(
        once=once,
        poll_interval_seconds=poll_interval_seconds,
        max_events=max_events,
    )


def process_inbox_event(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    event_path: Path,
    stats: DaemonStats | None = None,
) -> dict:
    return build_inbox_processing_service(
        repo_root,
        config,
        handlers={
            "conversation": lambda event: _process_conversation_event(
                repo_root=repo_root,
                config=config,
                event=event,
            ),
            "pull_request_merged": lambda event: _process_pull_request_merged_event(
                repo_root=repo_root,
                config=config,
                event=event,
            ),
        },
    ).process(event_path, stats=stats)


def _process_conversation_event(repo_root: Path, config: SisyphusConfig, event: dict) -> dict:
    gates = build_callable_task_execution_gate(
        repo_root,
        config,
        enforce_plan=enforce_plan_approved,
        enforce_spec=enforce_spec_frozen,
    )
    return build_conversation_event_service(
        repo_root,
        config,
        provider_runner=run_provider_wrapper,
        gates=gates,
    ).process(event)


def _process_pull_request_merged_event(repo_root: Path, config: SisyphusConfig, event: dict) -> dict:
    return build_pull_request_merged_event_service(repo_root, config).process(event)


def _new_event_id() -> str:
    return new_event_id()


def _is_internal_sisyphus_path(relative_path: str) -> bool:
    return is_internal_sisyphus_path(relative_path)
