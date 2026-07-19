from __future__ import annotations

from pathlib import Path

from .domain.task.strategy import (
    PLACEHOLDER_VALUES,
    SECTION_PATTERN,
    SUBSECTION_PATTERN,
    sync_test_strategy_from_content,
)


def sync_test_strategy_from_docs(task: dict, task_dir: Path) -> dict:
    source_name = "PLAN.md" if task["type"] == "feature" else "FIX_PLAN.md"
    source_path = task_dir / source_name
    if not source_path.exists():
        return task

    return sync_test_strategy_from_content(task, source_path.read_text(encoding="utf-8"))


__all__ = [
    "PLACEHOLDER_VALUES",
    "SECTION_PATTERN",
    "SUBSECTION_PATTERN",
    "sync_test_strategy_from_content",
    "sync_test_strategy_from_docs",
]
