from __future__ import annotations

from pathlib import Path

from ...application.planning_records import (
    collect_plan_gate_records,
    collect_spec_gate_records,
    current_plan_status,
    current_spec_status,
)
from ...application.results.planning import (
    PlanReviewOutcome,
    SpecFreezeOutcome,
    SubtaskGenerationOutcome,
)
from ...application.use_cases.planning import (
    PLAN_APPROVED,
    PLAN_CHANGES_REQUESTED,
    PLAN_PENDING_REVIEW,
    PLAN_REVIEW_LIMIT_REACHED,
    PLAN_STATUSES,
    SPEC_DRAFT,
    SPEC_FROZEN,
    SPEC_STATUSES,
    reopen_task_plan_for_design_replan as _reopen_task_plan_for_design_replan,
)
from ...composition.planning import build_planning_service
from ..config.loader import SisyphusConfig
from ..clock import SystemClock


def collect_plan_gates(task: dict, *, action: str) -> list[dict]:
    return collect_plan_gate_records(
        task,
        action=action,
        created_at=SystemClock().now(),
    )


def collect_spec_execution_gates(task: dict, *, action: str) -> list[dict]:
    return collect_spec_gate_records(
        task,
        action=action,
        created_at=SystemClock().now(),
    )


def approve_task_plan(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    reviewer: str,
    notes: str | None,
) -> PlanReviewOutcome:
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
    reviewer: str,
    notes: str | None,
) -> PlanReviewOutcome:
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
    author: str,
    notes: str | None,
) -> PlanReviewOutcome:
    return build_planning_service(repo_root, config).revise_plan(
        task_id,
        author=author,
        notes=notes,
    )


def enforce_plan_approved(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    action: str,
) -> tuple[bool, dict]:
    return build_planning_service(repo_root, config).enforce_plan_approved(
        task_id,
        action=action,
    )


def freeze_task_spec(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    reviewer: str,
    notes: str | None,
) -> SpecFreezeOutcome:
    return build_planning_service(repo_root, config).freeze_spec(
        task_id,
        reviewer=reviewer,
        notes=notes,
    )


def enforce_spec_frozen(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    action: str,
) -> tuple[bool, dict]:
    return build_planning_service(repo_root, config).enforce_spec_frozen(
        task_id,
        action=action,
    )


def generate_subtasks(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
) -> SubtaskGenerationOutcome:
    return build_planning_service(repo_root, config).generate_subtasks(task_id)


def reopen_task_plan_for_design_replan(
    task: dict,
    *,
    actor: str,
    notes: str | None,
) -> None:
    _reopen_task_plan_for_design_replan(
        task,
        actor=actor,
        notes=notes,
        clock=SystemClock(),
    )


__all__ = [
    "PLAN_APPROVED",
    "PLAN_CHANGES_REQUESTED",
    "PLAN_PENDING_REVIEW",
    "PLAN_REVIEW_LIMIT_REACHED",
    "PLAN_STATUSES",
    "SPEC_DRAFT",
    "SPEC_FROZEN",
    "SPEC_STATUSES",
    "PlanReviewOutcome",
    "SpecFreezeOutcome",
    "SubtaskGenerationOutcome",
    "approve_task_plan",
    "collect_plan_gates",
    "collect_spec_execution_gates",
    "current_plan_status",
    "current_spec_status",
    "enforce_plan_approved",
    "enforce_spec_frozen",
    "freeze_task_spec",
    "generate_subtasks",
    "reopen_task_plan_for_design_replan",
    "request_plan_changes",
    "revise_task_plan",
]
