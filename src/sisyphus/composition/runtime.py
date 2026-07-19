from __future__ import annotations

from pathlib import Path

from ..application.commands.task import CreateTaskRecordCommand
from ..application.results.inbox import DaemonStats
from ..application.results.task_creation import CreateOutcome
from ..infra.config.loader import SisyphusConfig
from ..infra.orchestration.workflow import run_workflow_cycle
from ..templates import materialize_task_templates
from .daemon import build_repository_inbox_processing_service
from .inbox import build_daemon_loop_service
from .task_creation import build_task_workspace_creation_service


def create_task_workspace(
    repo_root: Path,
    config: SisyphusConfig,
    task_type: str,
    slug: str,
) -> CreateOutcome:
    return build_task_workspace_creation_service(
        repo_root,
        config,
        template_materializer=materialize_task_templates,
    ).create(
        CreateTaskRecordCommand(
            task_type=task_type,
            slug=slug,
            spec_validation_required=True,
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
    processing = build_repository_inbox_processing_service(repo_root, config)
    return build_daemon_loop_service(
        repo_root,
        process_event=lambda event_path, stats: processing.process(
            event_path,
            stats=stats,
        ),
        workflow_cycle=lambda: run_workflow_cycle(repo_root, config),
    ).run(
        once=once,
        poll_interval_seconds=poll_interval_seconds,
        max_events=max_events,
    )


__all__ = ["create_task_workspace", "run_daemon"]
