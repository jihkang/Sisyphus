from __future__ import annotations

from pathlib import Path

from ...application.ports.workflow import TaskRecord
from ...config import SisyphusConfig
from ...conformance import mark_design_anchor
from ...shared.paths import task_dir as resolve_task_dir
from ...strategy import sync_test_strategy_from_docs
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
    def mark_design_anchor(self, task: TaskRecord, *, source: str) -> TaskRecord:
        return mark_design_anchor(task, source=source)


__all__ = [
    "DesignConformanceAdapter",
    "PlanningDocumentAdapter",
    "SpecValidationAdapter",
]
