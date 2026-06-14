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


@dataclass(frozen=True, slots=True)
class TransitionResult:
    allowed: bool
    action: LifecycleAction
    current_phase: str | None
    next_phase: str | None
    gates: tuple[dict, ...]
    reason: str

    @property
    def blocking_codes(self) -> tuple[str, ...]:
        return tuple(str(gate.get("code")) for gate in self.gates if gate.get("blocking", True))


__all__ = ["LifecycleAction", "TransitionResult", "WorkflowPhase"]
