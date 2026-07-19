from __future__ import annotations

from .factory import build_task_record, task_id_for
from .documents import render_brief, render_feature_plan, render_issue_fix_plan, render_issue_repro
from .models import DEFAULT_CHANGESET_PATH, DEFAULT_PROMOTION_RECEIPT_PATH, Task, default_task_docs


_REPOSITORY_EXPORTS = frozenset(
    {
        "ConcurrentTaskUpdateError",
        "ensure_task_record_defaults",
        "list_task_records",
        "load_task_record",
        "normalize_task_projection",
        "save_task_record",
        "sync_task_support_files",
        "update_task_record",
    }
)


def __getattr__(name: str) -> object:
    if name not in _REPOSITORY_EXPORTS:
        raise AttributeError(name)
    from . import repository

    return getattr(repository, name)

__all__ = [
    "ConcurrentTaskUpdateError",
    "DEFAULT_CHANGESET_PATH",
    "DEFAULT_PROMOTION_RECEIPT_PATH",
    "Task",
    "build_task_record",
    "default_task_docs",
    "ensure_task_record_defaults",
    "list_task_records",
    "load_task_record",
    "normalize_task_projection",
    "render_brief",
    "render_feature_plan",
    "render_issue_fix_plan",
    "render_issue_repro",
    "save_task_record",
    "sync_task_support_files",
    "task_id_for",
    "update_task_record",
]
