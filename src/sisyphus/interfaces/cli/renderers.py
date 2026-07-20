from __future__ import annotations

from ..conformance_presenter import extract_conformance_summary


def project_task_for_status_output(task: dict) -> dict:
    projected = dict(task)
    task_conformance = extract_conformance_summary(task)
    if task_conformance:
        projected["conformance_summary"] = task_conformance

    subtasks = task.get("subtasks")
    if isinstance(subtasks, list):
        projected["subtasks"] = [
            project_subtask_for_status_output(subtask) if isinstance(subtask, dict) else subtask
            for subtask in subtasks
        ]
    return projected


def project_subtask_for_status_output(subtask: dict) -> dict:
    projected = dict(subtask)
    subtask_conformance = extract_conformance_summary(subtask)
    if subtask_conformance:
        projected["conformance_summary"] = subtask_conformance
    return projected


__all__ = [
    "project_subtask_for_status_output",
    "project_task_for_status_output",
]
