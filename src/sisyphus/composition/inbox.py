from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import time

from ..application.ports.inbox import InboxEventHandler, InboxEventProcessor, Sleeper, WorkflowCycle
from ..application.use_cases.daemon_loop import DaemonLoopService
from ..application.use_cases.inbox import InboxQueueService
from ..application.use_cases.inbox_processing import InboxProcessingService
from ..infra.clock import SystemClock
from ..infra.config.loader import SisyphusConfig
from ..infra.daemon import JsonlDaemonEventLog
from ..infra.orchestration.common_adapters import EventPublisherAdapter
from ..infra.persistence import InboxRepository
from ..interfaces.inbox import inbox_event_to_record, parse_inbox_event


def _parse_event(raw: object) -> dict[str, object]:
    return inbox_event_to_record(parse_inbox_event(raw))


def build_inbox_queue_service(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    new_event_id: Callable[[], str],
) -> InboxQueueService:
    return InboxQueueService(
        inbox=InboxRepository(repo_root),
        parse_event=_parse_event,
        event_log=JsonlDaemonEventLog(repo_root),
        events=EventPublisherAdapter(repo_root, config),
        clock=SystemClock(),
        new_event_id=new_event_id,
    )


def build_inbox_processing_service(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    handlers: dict[str, InboxEventHandler],
) -> InboxProcessingService:
    return InboxProcessingService(
        inbox=InboxRepository(repo_root),
        parse_event=_parse_event,
        handlers=handlers,
        event_log=JsonlDaemonEventLog(repo_root),
        events=EventPublisherAdapter(repo_root, config),
        clock=SystemClock(),
    )


def build_daemon_loop_service(
    repo_root: Path,
    *,
    process_event: InboxEventProcessor,
    workflow_cycle: WorkflowCycle,
    sleeper: Sleeper = time.sleep,
) -> DaemonLoopService:
    return DaemonLoopService(
        inbox=InboxRepository(repo_root),
        process_event=process_event,
        workflow_cycle=workflow_cycle,
        sleep=sleeper,
    )


__all__ = [
    "build_daemon_loop_service",
    "build_inbox_processing_service",
    "build_inbox_queue_service",
]
