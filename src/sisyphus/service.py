from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .application.results.service_runtime import ServiceStepResult, TaskNotification
from .composition.service_runtime import (
    run_service as run_repository_service,
    run_service_step as run_repository_service_step,
)
from .config import SisyphusConfig
from .interfaces.conformance_presenter import (
    extract_conformance_summary,
    format_conformance_summary,
    summarize_subtask_conformance,
)
from .promotion_state import promotion_status_summary


@dataclass(slots=True)
class TaskSnapshot:
    fingerprint: tuple[object, ...]
    task_conformance: str | None = None
    subtask_conformance: str | None = None
    subtasks: tuple[tuple[str, object, str | None], ...] = ()


class TaskNotificationTracker:
    def __init__(self) -> None:
        self._snapshots: dict[str, TaskSnapshot] = {}

    def collect(self, tasks: list[dict]) -> list[TaskNotification]:
        notifications: list[TaskNotification] = []
        seen: set[str] = set()
        for task in tasks:
            task_id = str(task.get("id"))
            seen.add(task_id)
            meta = task.get("meta", {}) if isinstance(task.get("meta"), dict) else {}
            source_context = dict(meta.get("source_context") or {})
            if not source_context:
                continue
            snapshot = _task_snapshot(task)
            previous = self._snapshots.get(task_id)
            self._snapshots[task_id] = snapshot
            if previous is not None and previous.fingerprint == snapshot.fingerprint:
                continue
            notifications.append(
                TaskNotification(
                    task_id=task_id,
                    summary=build_task_update_summary(task, previous_snapshot=previous),
                    source_context=source_context,
                )
            )

        stale = set(self._snapshots) - seen
        for task_id in stale:
            self._snapshots.pop(task_id, None)
        return notifications


def run_service_step(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    tracker: TaskNotificationTracker | None = None,
    max_events: int | None = None,
) -> ServiceStepResult:
    return run_repository_service_step(
        repo_root,
        config,
        tracker=tracker,
        max_events=max_events,
    )


def run_service(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    poll_interval_seconds: int,
    tracker: TaskNotificationTracker | None = None,
    notifier: Callable[[TaskNotification], None] | None = None,
) -> None:
    run_repository_service(
        repo_root,
        config,
        poll_interval_seconds=poll_interval_seconds,
        tracker=tracker,
        notifier=notifier,
    )


def build_task_update_summary(task: dict, previous_snapshot: TaskSnapshot | None = None) -> str:
    subtasks = task.get("subtasks", [])
    if not isinstance(subtasks, list):
        subtasks = []
    completed = sum(
        1 for subtask in subtasks if isinstance(subtask, dict) and subtask.get("status") == "completed"
    )
    total = len(subtasks)
    subtask_entries = _subtask_conformance_entries(task)
    meta = task.get("meta", {}) if isinstance(task.get("meta"), dict) else {}
    requested_slug = meta.get("requested_slug")
    followup_of_task_id = meta.get("followup_of_task_id")
    followup_segment = ""
    if followup_of_task_id:
        followup_segment = f" requested_slug={requested_slug or task.get('slug')} followup_of={followup_of_task_id}"
    task_conformance = format_conformance_summary(extract_conformance_summary(task))
    subtask_conformance = summarize_subtask_conformance(task)
    promotion_status = promotion_status_summary(task)
    task_transition = None
    subtask_transition = None
    if previous_snapshot is not None:
        task_transition = _format_transition(previous_snapshot.task_conformance, task_conformance, "conformance_transition")
        subtask_transition = _format_transition(
            previous_snapshot.subtask_conformance,
            subtask_conformance,
            "subtask_conformance_transition",
        )
        subtask_detail_transition = _format_subtask_transition(previous_snapshot.subtasks, subtask_entries)
    else:
        subtask_detail_transition = None
    return (
        f"{task.get('id')} "
        f"status={task.get('status')} "
        f"phase={task.get('workflow_phase')} "
        f"plan={task.get('plan_status')} "
        f"spec={task.get('spec_status')} "
        f"{f'promotion={promotion_status} ' if promotion_status else ''}"
        f"subtasks={completed}/{total}"
        f"{followup_segment}"
        f"{f' conformance={task_conformance}' if task_conformance else ''}"
        f"{f' {task_transition}' if task_transition else ''}"
        f"{f' subtask_conformance={subtask_conformance}' if subtask_conformance else ''}"
        f"{f' {subtask_transition}' if subtask_transition else ''}"
        f"{f' {subtask_detail_transition}' if subtask_detail_transition else ''}"
    )


def _task_snapshot(task: dict) -> TaskSnapshot:
    gates = tuple(sorted(gate.get("code") for gate in task.get("gates", [])))
    task_conformance = format_conformance_summary(extract_conformance_summary(task))
    promotion_status = promotion_status_summary(task)
    subtasks = _subtask_conformance_entries(task)
    fingerprint = (
        task.get("status"),
        task.get("workflow_phase"),
        task.get("plan_status"),
        task.get("spec_status"),
        promotion_status,
        gates,
        task_conformance,
        subtasks,
    )
    return TaskSnapshot(
        fingerprint=fingerprint,
        task_conformance=task_conformance,
        subtask_conformance=summarize_subtask_conformance(task),
        subtasks=subtasks,
    )


def _format_transition(previous: str | None, current: str | None, label: str) -> str | None:
    if previous in (None, "") or current in (None, "") or previous == current:
        return None
    return f"{label}={previous} -> {current}"


def _subtask_conformance_entries(task: dict) -> tuple[tuple[str, object, str | None], ...]:
    subtasks = task.get("subtasks")
    if not isinstance(subtasks, list):
        return ()
    return tuple(
        (
            str(subtask.get("id")),
            subtask.get("status"),
            format_conformance_summary(extract_conformance_summary(subtask)),
        )
        for subtask in subtasks
        if isinstance(subtask, dict)
    )


def _format_subtask_transition(
    previous: tuple[tuple[str, object, str | None], ...],
    current: tuple[tuple[str, object, str | None], ...],
) -> str | None:
    previous_map = {subtask_id: (status, conformance) for subtask_id, status, conformance in previous}
    current_map = {subtask_id: (status, conformance) for subtask_id, status, conformance in current}
    changed: list[str] = []
    for subtask_id in sorted(set(previous_map) | set(current_map)):
        previous_state = previous_map.get(subtask_id)
        current_state = current_map.get(subtask_id)
        if previous_state == current_state:
            continue
        if previous_state is None:
            changed.append(f"{subtask_id}:new {current_state[0]} {current_state[1] or '-'}")
            continue
        if current_state is None:
            changed.append(f"{subtask_id}:removed {previous_state[0]} {previous_state[1] or '-'}")
            continue
        changed.append(
            f"{subtask_id}:{previous_state[0]} {previous_state[1] or '-'} -> "
            f"{current_state[0]} {current_state[1] or '-'}"
        )
    if not changed:
        return None
    return f"subtask_conformance_changes={', '.join(changed)}"
