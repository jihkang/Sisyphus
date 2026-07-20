from __future__ import annotations

from ..gates import GateSpec
from .models import PlanReviewState, PlanStatus, SpecState, SpecStatus


def collect_plan_gate_specs(
    state: PlanReviewState,
    *,
    action: str,
) -> tuple[GateSpec, ...]:
    if state.review_round >= state.max_review_rounds and state.status != PlanStatus.APPROVED:
        return (
            GateSpec(
                "PLAN_REVIEW_LIMIT_REACHED",
                f"task plan review exceeded maximum rounds before {action}",
                "plan",
            ),
        )
    if state.status == PlanStatus.APPROVED:
        return ()
    if state.status == PlanStatus.CHANGES_REQUESTED:
        return (
            GateSpec(
                "PLAN_CHANGES_REQUESTED",
                f"task plan has requested changes before {action}",
                "plan",
            ),
        )
    return (
        GateSpec(
            "PLAN_APPROVAL_REQUIRED",
            f"task plan must be approved before {action}",
            "plan",
        ),
    )


def collect_spec_gate_specs(
    state: SpecState,
    *,
    action: str,
) -> tuple[GateSpec, ...]:
    if state.status == SpecStatus.FROZEN:
        return ()
    return (
        GateSpec(
            "SPEC_FREEZE_REQUIRED",
            f"task spec must be frozen before {action}",
            "spec",
        ),
    )


__all__ = ["collect_plan_gate_specs", "collect_spec_gate_specs"]
