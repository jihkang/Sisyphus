from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ..ports.workflow import TaskRecord
from ..results.inbox import DaemonStats
from ..results.service_runtime import ServiceStepResult, TaskNotification


class NotificationCollector(Protocol):
    def collect(self, tasks: list[TaskRecord]) -> list[TaskNotification]: ...


DaemonStep = Callable[[int | None], DaemonStats]
TaskRecordQuery = Callable[[], list[TaskRecord]]
NotificationSink = Callable[[TaskNotification], None]
Sleeper = Callable[[float], None]


@dataclass(slots=True)
class ServiceRuntime:
    daemon_step: DaemonStep
    list_tasks: TaskRecordQuery
    sleep: Sleeper

    def step(
        self,
        *,
        tracker: NotificationCollector | None = None,
        max_events: int | None = None,
    ) -> ServiceStepResult:
        stats = self.daemon_step(max_events)
        notifications: list[TaskNotification] = []
        if tracker is not None:
            tasks = sorted(
                self.list_tasks(),
                key=lambda task: task.get("updated_at", ""),
            )
            notifications = tracker.collect(tasks)
        return ServiceStepResult(stats=stats, notifications=notifications)

    def run(
        self,
        *,
        poll_interval_seconds: int,
        tracker: NotificationCollector | None = None,
        notifier: NotificationSink | None = None,
    ) -> None:
        while True:
            result = self.step(tracker=tracker)
            if notifier is not None:
                for notification in result.notifications:
                    notifier(notification)
            if not result.progressed:
                self.sleep(max(poll_interval_seconds, 1))


__all__ = ["NotificationCollector", "ServiceRuntime"]
