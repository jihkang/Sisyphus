from __future__ import annotations

from dataclasses import dataclass, field

from .inbox import DaemonStats


@dataclass(slots=True)
class TaskNotification:
    task_id: str
    summary: str
    source_context: dict[str, object]


@dataclass(slots=True)
class ServiceStepResult:
    stats: DaemonStats
    notifications: list[TaskNotification] = field(default_factory=list)

    @property
    def progressed(self) -> bool:
        return any(
            (
                self.stats.processed,
                self.stats.failed,
                self.stats.skipped,
                self.stats.orchestrated,
                self.notifications,
            )
        )


__all__ = ["ServiceStepResult", "TaskNotification"]
