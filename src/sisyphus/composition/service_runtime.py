from __future__ import annotations

from pathlib import Path
import time

from ..application.results.service_runtime import ServiceStepResult, TaskNotification
from ..application.use_cases.service_runtime import NotificationCollector, ServiceRuntime
from ..infra.config.loader import SisyphusConfig
from .repository_requests import build_task_record_query_service
from .runtime import run_daemon


def build_service_runtime(repo_root: Path, config: SisyphusConfig) -> ServiceRuntime:
    queries = build_task_record_query_service(repo_root, config)
    return ServiceRuntime(
        daemon_step=lambda max_events: run_daemon(
            repo_root,
            config,
            once=True,
            poll_interval_seconds=1,
            max_events=max_events,
        ),
        list_tasks=queries.list,
        sleep=time.sleep,
    )


def run_service_step(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    tracker: NotificationCollector | None = None,
    max_events: int | None = None,
) -> ServiceStepResult:
    return build_service_runtime(repo_root, config).step(
        tracker=tracker,
        max_events=max_events,
    )


def run_service(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    poll_interval_seconds: int,
    tracker: NotificationCollector | None = None,
    notifier=None,
) -> None:
    build_service_runtime(repo_root, config).run(
        poll_interval_seconds=poll_interval_seconds,
        tracker=tracker,
        notifier=notifier,
    )


__all__ = ["build_service_runtime", "run_service", "run_service_step"]
