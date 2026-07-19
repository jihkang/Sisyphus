from __future__ import annotations

from typing import Protocol

from .workflow import TaskRecord


class PlanningDocumentPort(Protocol):
    def sync_strategy(self, task_id: str, task: TaskRecord) -> TaskRecord: ...


class SpecValidationPort(Protocol):
    def required(self, task_id: str, task: TaskRecord) -> bool: ...

    def collect_gates(
        self,
        task_id: str,
        task: TaskRecord,
        *,
        action: str,
        refresh: bool = False,
        require_existing_report: bool = False,
    ) -> tuple[dict, ...]: ...


class DesignConformancePort(Protocol):
    def mark_design_anchor(self, task: TaskRecord, *, source: str) -> TaskRecord: ...


__all__ = [
    "DesignConformancePort",
    "PlanningDocumentPort",
    "SpecValidationPort",
]
