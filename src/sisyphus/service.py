from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
import time

from .config import SisyphusConfig
from .daemon import DaemonStats, run_daemon
from .promotion_state import promotion_status_summary
from .state import list_task_records


@dataclass(slots=True)
class TaskSnapshot:
    fingerprint: tuple[object, ...]
    task_conformance: str | None = None
    subtask_conformance: str | None = None
    subtasks: tuple[tuple[str, object, str | None], ...] = ()


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
    config: SisyphusConfig,
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


def extract_conformance_summary(entity: dict) -> dict[str, object] | None:
    conformance = entity.get("conformance")
    if not isinstance(conformance, dict):
        meta = entity.get("meta")
        if isinstance(meta, dict):
            conformance = meta.get("conformance")
    if not isinstance(conformance, dict):
        return None

    summary: dict[str, object] = {}
    aliases: dict[str, tuple[str, ...]] = {
        "status": ("status", "color"),
        "last_spec_anchor_at": ("last_spec_anchor_at", "spec_anchor_at", "anchored_at"),
        "last_checkpoint_type": ("last_checkpoint_type", "checkpoint_type", "checkpoint"),
        "drift_count": ("drift_count", "drifts", "drift"),
        "summary": ("summary", "last_summary", "message"),
    }
    for target_key, candidate_keys in aliases.items():
        for candidate_key in candidate_keys:
            value = conformance.get(candidate_key)
            if value not in (None, ""):
                summary[target_key] = value
                break
    if not summary:
        return None
    return summary


def format_conformance_summary(summary: dict[str, object] | None) -> str | None:
    if not summary:
        return None
    parts: list[str] = []
    status = summary.get("status")
    if status not in (None, ""):
        parts.append(str(status))
    anchor = summary.get("last_spec_anchor_at")
    if anchor not in (None, ""):
        parts.append(f"anchor={anchor}")
    checkpoint = summary.get("last_checkpoint_type")
    if checkpoint not in (None, ""):
        parts.append(f"checkpoint={checkpoint}")
    drift_count = summary.get("drift_count")
    if drift_count not in (None, ""):
        parts.append(f"drift={drift_count}")
    note = summary.get("summary")
    if note not in (None, ""):
        parts.append(f"note={note}")
    return " ".join(parts)


def summarize_subtask_conformance(task: dict) -> str | None:
    subtasks = task.get("subtasks")
    if not isinstance(subtasks, list):
        return None
    counts: dict[str, int] = {}
    for subtask in subtasks:
        if not isinstance(subtask, dict):
            continue
        summary = extract_conformance_summary(subtask)
        if summary is None:
            continue
        status = str(summary.get("status") or "unknown").lower()
        counts[status] = counts.get(status, 0) + 1
    if not counts:
        return None
    order = ("green", "yellow", "red", "unknown")
    parts = [f"{status}:{counts[status]}" for status in order if counts.get(status)]
    parts.extend(
        f"{status}:{count}"
        for status, count in sorted(counts.items())
        if status not in order
    )
    return " ".join(parts)


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
