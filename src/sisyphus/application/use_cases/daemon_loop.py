from __future__ import annotations

from dataclasses import dataclass

from ..ports.inbox import (
    InboxEventProcessor,
    InboxRepositoryPort,
    Sleeper,
    WorkflowCycle,
)
from ..results.inbox import DaemonStats


@dataclass(slots=True)
class DaemonLoopService:
    inbox: InboxRepositoryPort
    process_event: InboxEventProcessor
    workflow_cycle: WorkflowCycle
    sleep: Sleeper

    def run(
        self,
        *,
        once: bool,
        poll_interval_seconds: int,
        max_events: int | None = None,
    ) -> DaemonStats:
        stats = DaemonStats()
        while True:
            available = self.inbox.list_processable()
            progressed = False

            for event_path in available:
                try:
                    self.process_event(event_path, stats)
                except FileNotFoundError:
                    stats.skipped += 1
                    continue
                progressed = True
                if max_events is not None and (stats.processed + stats.failed) >= max_events:
                    return stats

            orchestrated = self.workflow_cycle()
            if orchestrated:
                stats.orchestrated += orchestrated
                progressed = True

            if once and not progressed:
                return stats
            if once:
                continue
            if not progressed:
                self.sleep(max(poll_interval_seconds, 1))


__all__ = ["DaemonLoopService"]
