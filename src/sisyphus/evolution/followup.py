from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ..utils import required_str


EVOLUTION_FOLLOWUP_SOURCE_CONTEXT_KIND = "evolution_followup"


def extract_followup_source_context(
    task: Mapping[str, object],
    *,
    purpose: str,
) -> dict[str, object]:
    meta = task.get("meta")
    if not isinstance(meta, Mapping):
        raise ValueError(f"task.meta is required for evolution follow-up {purpose}")
    source_context = meta.get("source_context")
    if not isinstance(source_context, Mapping):
        raise ValueError(
            f"task.meta.source_context is required for evolution follow-up {purpose}"
        )
    followup_context = source_context.get(EVOLUTION_FOLLOWUP_SOURCE_CONTEXT_KIND)
    if not isinstance(followup_context, Mapping):
        raise ValueError("task is not an evolution follow-up task")
    return dict(followup_context)


def relative_task_locator(*, task: Mapping[str, object], relative_path: str) -> str:
    task_dir = required_str(task.get("task_dir"), "task.task_dir")
    return (Path(task_dir) / relative_path).as_posix()
