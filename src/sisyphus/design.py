from __future__ import annotations

from pathlib import Path

from .domain.task.design import *  # noqa: F403
from .domain.task.design import __all__ as _DOMAIN_EXPORTS
from .domain.task.design import sync_design_from_content


def sync_design_from_docs(task: dict, task_dir: Path, *, source_name: str) -> dict:
    source_path = task_dir / source_name
    if not source_path.exists():
        return task
    return sync_design_from_content(task, source_path.read_text(encoding="utf-8"))


__all__ = [*_DOMAIN_EXPORTS, "sync_design_from_docs"]
