from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
import time

from .config import TaskflowConfig
from .daemon import DaemonStats, run_daemon
from .state import list_task_records


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


class TaskNotificationTracker:
    def __init__(self) -> None:
        self._snapshots: dict[str, tuple[object, ...]] = {}

    def collect(self, tasks: list[dict]) -> list[TaskNotification]:
        notifications: list[TaskNotification] = []
        seen: set[str] = set()
        for task in tasks:
            task_id = str(task.get("id"))
            seen.add(task_id)
            source_context = dict(task.get("meta", {}).get("source_context") or {})
            if not source_context:
                continue
            fingerprint = _task_fingerprint(task)
            previous = self._snapshots.get(task_id)
            self._snapshots[task_id] = fingerprint
            if previous == fingerprint:
                continue
            notifications.append(
                TaskNotification(
                    task_id=task_id,
                    summary=build_task_update_summary(task),
                    source_context=source_context,
                )
            )

        stale = set(self._snapshots) - seen
        for task_id in stale:
            self._snapshots.pop(task_id, None)
        return notifications


def run_service_step(
    repo_root: Path,
    config: TaskflowConfig,
    *,
    tracker: TaskNotificationTracker | None = None,
    max_events: int | None = None,
) -> ServiceStepResult:
    stats = run_daemon(
        repo_root=repo_root,
        config=config,
        once=True,
        poll_interval_seconds=1,
        max_events=max_events,
    )
    notifications: list[TaskNotification] = []
    if tracker is not None:
        tasks = sorted(
            list_task_records(repo_root=repo_root, task_dir_name=config.task_dir),
            key=lambda task: task.get("updated_at", ""),
        )
        notifications = tracker.collect(tasks)
    return ServiceStepResult(stats=stats, notifications=notifications)


def run_service(
    repo_root: Path,
    config: TaskflowConfig,
    *,
    poll_interval_seconds: int,
    tracker: TaskNotificationTracker | None = None,
    notifier: Callable[[TaskNotification], None] | None = None,
) -> None:
    while True:
        result = run_service_step(repo_root=repo_root, config=config, tracker=tracker)
        if notifier is not None:
            for notification in result.notifications:
                notifier(notification)
        if not result.progressed:
            time.sleep(max(poll_interval_seconds, 1))


def build_task_update_summary(task: dict) -> str:
    completed = sum(1 for subtask in task.get("subtasks", []) if subtask.get("status") == "completed")
    total = len(task.get("subtasks", []))
    return (
        f"{task.get('id')} "
        f"status={task.get('status')} "
        f"phase={task.get('workflow_phase')} "
        f"plan={task.get('plan_status')} "
        f"spec={task.get('spec_status')} "
        f"subtasks={completed}/{total}"
    )


def _task_fingerprint(task: dict) -> tuple[object, ...]:
    gates = tuple(sorted(gate.get("code") for gate in task.get("gates", [])))
    subtasks = tuple(
        (str(subtask.get("id")), subtask.get("status"))
        for subtask in task.get("subtasks", [])
    )
    return (
        task.get("status"),
        task.get("workflow_phase"),
        task.get("plan_status"),
        task.get("spec_status"),
        gates,
        subtasks,
    )
