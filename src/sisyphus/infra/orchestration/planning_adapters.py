from __future__ import annotations

from pathlib import Path
import uuid

from ...application.ports.clock import ClockPort
from ...application.ports.workflow import TaskRecord
from ...domain.task.conformance import (
    CONFORMANCE_CHECKPOINT_DESIGN_ANCHOR,
    CONFORMANCE_GREEN,
    append_conformance_entry,
)
from ...domain.task.design import ensure_task_design_defaults, summarize_design_anchor
from ...shared.paths import task_dir as resolve_task_dir
from ..config.loader import SisyphusConfig
from ..documents.task_strategy import sync_test_strategy_from_docs
from ..validation.spec_validation import collect_spec_validation_gates, spec_validation_required


class PlanningDocumentAdapter:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._repo_root = repo_root
        self._config = config

    def sync_strategy(self, task_id: str, task: TaskRecord) -> TaskRecord:
        directory = resolve_task_dir(self._repo_root, self._config.task_dir, task_id)
        return sync_test_strategy_from_docs(task=task, task_dir=directory)


class SpecValidationAdapter:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._repo_root = repo_root
        self._config = config

    def required(self, task_id: str, task: TaskRecord) -> bool:
        directory = resolve_task_dir(self._repo_root, self._config.task_dir, task_id)
        return spec_validation_required(task, directory)

    def collect_gates(
        self,
        task_id: str,
        task: TaskRecord,
        *,
        action: str,
        refresh: bool = False,
        require_existing_report: bool = False,
    ) -> tuple[dict, ...]:
        directory = resolve_task_dir(self._repo_root, self._config.task_dir, task_id)
        return tuple(
            collect_spec_validation_gates(
                task=task,
                task_dir=directory,
                action=action,
                refresh=refresh,
                require_existing_report=require_existing_report,
            )
        )


class DesignConformanceAdapter:
    def __init__(self, clock: ClockPort) -> None:
        self._clock = clock

    def mark_design_anchor(self, task: TaskRecord, *, source: str) -> TaskRecord:
        ensure_task_design_defaults(task)
        design = task["design"]
        return append_conformance_entry(
            task,
            checkpoint_type=CONFORMANCE_CHECKPOINT_DESIGN_ANCHOR,
            status=CONFORMANCE_GREEN,
            timestamp=self._clock.now(),
            task_event_id=uuid.uuid4().hex,
            summary=summarize_design_anchor(design.get("frozen", {}) or design),
            source=source,
            resolved=False,
            drift=0,
        )


__all__ = [
    "DesignConformanceAdapter",
    "PlanningDocumentAdapter",
    "SpecValidationAdapter",
]
