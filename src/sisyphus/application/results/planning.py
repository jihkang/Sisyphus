from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PlanReviewOutcome:
    task_id: str
    plan_status: str
    task_status: str
    gates: list[dict]


@dataclass(slots=True)
class SpecFreezeOutcome:
    task_id: str
    spec_status: str
    task_status: str
    workflow_phase: str


@dataclass(slots=True)
class SubtaskGenerationOutcome:
    task_id: str
    workflow_phase: str
    subtasks: list[dict]


__all__ = ["PlanReviewOutcome", "SpecFreezeOutcome", "SubtaskGenerationOutcome"]
