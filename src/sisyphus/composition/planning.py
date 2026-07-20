from __future__ import annotations

from pathlib import Path

from ..application.use_cases.planning import PlanningService
from ..infra.clock import SystemClock
from ..infra.config.loader import SisyphusConfig
from ..infra.orchestration.planning_adapters import (
    DesignConformanceAdapter,
    PlanningDocumentAdapter,
    SpecValidationAdapter,
)
from ..infra.orchestration.common_adapters import FileTaskRecordAdapter, ManualInterventionAdapter


def build_planning_service(repo_root: Path, config: SisyphusConfig) -> PlanningService:
    clock = SystemClock()
    return PlanningService(
        tasks=FileTaskRecordAdapter(repo_root, config),
        documents=PlanningDocumentAdapter(repo_root, config),
        validation=SpecValidationAdapter(repo_root, config),
        design_conformance=DesignConformanceAdapter(clock),
        interventions=ManualInterventionAdapter(repo_root, config),
        clock=clock,
    )


def approve_task_plan(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    reviewer: str = "operator",
    notes: str | None = None,
):
    return build_planning_service(repo_root, config).approve_plan(
        task_id,
        reviewer=reviewer,
        notes=notes,
    )


def request_plan_changes(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    reviewer: str = "operator",
    notes: str | None = None,
):
    return build_planning_service(repo_root, config).request_changes(
        task_id,
        reviewer=reviewer,
        notes=notes,
    )


def revise_task_plan(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    author: str = "operator",
    notes: str | None = None,
):
    return build_planning_service(repo_root, config).revise_plan(
        task_id,
        author=author,
        notes=notes,
    )


def freeze_task_spec(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    reviewer: str = "operator",
    notes: str | None = None,
):
    return build_planning_service(repo_root, config).freeze_spec(
        task_id,
        reviewer=reviewer,
        notes=notes,
    )


def validate_task_spec(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    persist: bool = True,
):
    return build_planning_service(repo_root, config).validate_spec(
        task_id,
        persist=persist,
    )


def generate_subtasks(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
):
    return build_planning_service(repo_root, config).generate_subtasks(task_id)


__all__ = [
    "approve_task_plan",
    "build_planning_service",
    "freeze_task_spec",
    "generate_subtasks",
    "request_plan_changes",
    "revise_task_plan",
    "validate_task_spec",
]
