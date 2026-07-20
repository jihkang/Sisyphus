from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..gates import GateSpec, dedupe_gate_specs
from ..planning.models import PlanStatus, SpecStatus


class WorkflowPhase(str, Enum):
    PLAN_IN_REVIEW = "plan_in_review"
    PLAN_REVISION = "plan_revision"
    NEEDS_USER_INPUT = "needs_user_input"
    SPEC_DRAFTING = "spec_drafting"
    SPEC_IN_REVIEW = "spec_in_review"
    SUBTASK_PLANNING = "subtask_planning"
    EXECUTION = "execution"
    INTEGRATION_REVIEW = "integration_review"
    VERIFIED = "verified"
    PROMOTION_PENDING = "promotion_pending"
    RETARGET_REQUIRED = "retarget_required"
    CLOSED = "closed"


class LifecycleAction(str, Enum):
    APPROVE_PLAN = "approve_plan"
    REQUEST_PLAN_CHANGES = "request_plan_changes"
    REVISE_PLAN = "revise_plan"
    FREEZE_SPEC = "freeze_spec"
    GENERATE_SUBTASKS = "generate_subtasks"
    START_EXECUTION = "start_execution"
    VERIFY = "verify"
    CLOSE = "close"
    EXECUTE_PROMOTION = "execute_promotion"
    RECORD_MERGED_PR = "record_merged_pr"


@dataclass(frozen=True, slots=True)
class SubtaskConformance:
    subtask_id: str | None
    status: str
    unresolved_warning_count: int = 0
    last_checkpoint_type: str | None = None


@dataclass(frozen=True, slots=True)
class ConformanceState:
    status: str = "green"
    unresolved_warning_count: int = 0
    last_checkpoint_type: str | None = None
    subtasks: tuple[SubtaskConformance, ...] = ()


@dataclass(frozen=True, slots=True)
class PromotionState:
    required: bool = False
    status: str | None = None

    @property
    def is_complete(self) -> bool:
        return not self.required or self.status in {"not_required", "promotion_recorded"}


@dataclass(frozen=True, slots=True)
class LifecycleSnapshot:
    current_phase: str | None
    closed: bool
    plan_status: PlanStatus
    plan_review_round: int
    max_plan_review_rounds: int
    spec_status: SpecStatus
    verify_status: str
    conformance: ConformanceState = ConformanceState()
    promotion: PromotionState = PromotionState()


@dataclass(frozen=True, slots=True)
class TransitionDecision:
    allowed: bool
    action: LifecycleAction
    current_phase: str | None
    next_phase: str | None
    gates: tuple[GateSpec, ...]
    reason: str

    @property
    def blocking_codes(self) -> tuple[str, ...]:
        return tuple(gate.code for gate in self.gates if gate.blocking)


__all__ = [
    "ConformanceState",
    "GateSpec",
    "LifecycleAction",
    "LifecycleSnapshot",
    "PlanStatus",
    "PromotionState",
    "SpecStatus",
    "SubtaskConformance",
    "TransitionDecision",
    "WorkflowPhase",
    "dedupe_gate_specs",
]
