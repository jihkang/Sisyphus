from __future__ import annotations

from .domain.task.strategy import (
    PLACEHOLDER_VALUES,
    SECTION_PATTERN,
    SUBSECTION_PATTERN,
    sync_test_strategy_from_content,
)
from .infra.documents.task_strategy import sync_test_strategy_from_docs


__all__ = [
    "PLACEHOLDER_VALUES",
    "SECTION_PATTERN",
    "SUBSECTION_PATTERN",
    "sync_test_strategy_from_content",
    "sync_test_strategy_from_docs",
]
