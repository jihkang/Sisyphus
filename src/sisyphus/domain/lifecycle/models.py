from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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


class PlanStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"


class SpecStatus(str, Enum):
    DRAFT = "draft"
    FROZEN = "frozen"


@dataclass(frozen=True, slots=True)
class GateSpec:
    code: str
    message: str
    source: str
    blocking: bool = True
    severity: str | None = None
    checkpoint_type: str | None = None
    subtask_id: str | None = None

    @property
    def identity(self) -> tuple[str, str, str | None, str | None]:
        return (self.code, self.message, self.checkpoint_type, self.subtask_id)


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


def dedupe_gate_specs(gates: tuple[GateSpec, ...] | list[GateSpec]) -> tuple[GateSpec, ...]:
    seen: set[tuple[str, str, str | None, str | None]] = set()
    result: list[GateSpec] = []
    for gate in gates:
        if gate.identity in seen:
            continue
        seen.add(gate.identity)
        result.append(gate)
    return tuple(result)


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
