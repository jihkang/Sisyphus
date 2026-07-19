from __future__ import annotations

from .models import (
    GateSpec,
    LifecycleAction,
    LifecycleSnapshot,
    PlanStatus,
    TransitionDecision,
    dedupe_gate_specs,
)
from ..planning.models import PlanReviewState, SpecState
from ..planning.policy import collect_plan_gate_specs, collect_spec_gate_specs


HUMAN_GATED_ACTIONS = frozenset(
    {
        LifecycleAction.APPROVE_PLAN,
        LifecycleAction.FREEZE_SPEC,
        LifecycleAction.EXECUTE_PROMOTION,
        LifecycleAction.RECORD_MERGED_PR,
    }
)


def evaluate_lifecycle_policy(
    snapshot: LifecycleSnapshot,
    action: LifecycleAction,
) -> TransitionDecision:
    if snapshot.closed and action != LifecycleAction.CLOSE:
        return _blocked(
            snapshot,
            action,
            _gate("TASK_CLOSED", "closed tasks do not accept lifecycle transitions", "lifecycle"),
            reason="Task is already closed.",
        )

    if action == LifecycleAction.APPROVE_PLAN:
        return _allowed(snapshot, action, "spec_drafting", "Plan approval is a review-gated transition.")

    if action == LifecycleAction.REQUEST_PLAN_CHANGES:
        return _allowed(snapshot, action, "plan_revision", "Plan changes can be requested by a reviewer.")

    if action == LifecycleAction.REVISE_PLAN:
        if snapshot.plan_status != PlanStatus.CHANGES_REQUESTED:
            return _blocked(
                snapshot,
                action,
                _gate("PLAN_REVISION_NOT_REQUESTED", "plan revision requires requested changes", "plan"),
                reason="Plan revision is only valid after review requests changes.",
            )
        return _allowed(snapshot, action, "plan_in_review", "Plan revision resubmits the task for review.")

    if action == LifecycleAction.FREEZE_SPEC:
        gates = list(_plan_gates(snapshot, action_label="spec freeze"))
        if gates:
            return _blocked(
                snapshot,
                action,
                *gates,
                reason="Spec cannot be frozen before plan approval.",
            )
        return _allowed(snapshot, action, "subtask_planning", "Spec freeze is allowed after plan approval.")

    if action == LifecycleAction.GENERATE_SUBTASKS:
        gates = _execution_readiness_gates(
            snapshot,
            action_label="subtask generation",
            include_conformance=False,
        )
        if gates:
            return _blocked(
                snapshot,
                action,
                *gates,
                reason="Subtasks require an approved plan and frozen spec.",
            )
        return _allowed(snapshot, action, "execution", "Subtask generation is allowed.")

    if action == LifecycleAction.START_EXECUTION:
        gates = _execution_readiness_gates(snapshot, action_label="execution")
        if gates:
            return _blocked(
                snapshot,
                action,
                *gates,
                reason="Execution requires an approved, frozen, conformant task.",
            )
        return _allowed(snapshot, action, "execution", "Execution is allowed.")

    if action == LifecycleAction.VERIFY:
        gates = list(_plan_gates(snapshot, action_label="verify"))
        gates.extend(_spec_gates(snapshot, action_label="verify"))
        gates.extend(_conformance_gates(snapshot, action_label="verify"))
        if gates:
            return _blocked(snapshot, action, *gates, reason="Verification is blocked by lifecycle gates.")
        return _allowed(snapshot, action, "verified", "Verification may run.")

    if action == LifecycleAction.CLOSE:
        gates = _close_gates(snapshot)
        if gates:
            return _blocked(snapshot, action, *gates, reason="Close is blocked until lifecycle gates clear.")
        return _allowed(snapshot, action, "closed", "Close is allowed.")

    if action == LifecycleAction.EXECUTE_PROMOTION:
        gates = _promotion_gates(snapshot)
        if gates:
            return _blocked(snapshot, action, *gates, reason="Promotion execution is blocked.")
        return _allowed(snapshot, action, "promotion_pending", "Promotion execution is human-gated.")

    if action == LifecycleAction.RECORD_MERGED_PR:
        return _allowed(snapshot, action, snapshot.current_phase, "Recording a merged PR is human-gated.")

    return _blocked(
        snapshot,
        action,
        _gate("UNKNOWN_LIFECYCLE_ACTION", f"unsupported lifecycle action: {action}", "lifecycle"),
        reason="Unsupported lifecycle action.",
    )


def _execution_readiness_gates(
    snapshot: LifecycleSnapshot,
    *,
    action_label: str,
    include_conformance: bool = True,
) -> list[GateSpec]:
    gates = list(_plan_gates(snapshot, action_label=action_label))
    gates.extend(_spec_gates(snapshot, action_label=action_label))
    if include_conformance:
        gates.extend(_conformance_gates(snapshot, action_label=action_label))
    return list(dedupe_gate_specs(gates))


def _plan_gates(snapshot: LifecycleSnapshot, *, action_label: str) -> tuple[GateSpec, ...]:
    return collect_plan_gate_specs(
        PlanReviewState(
            status=snapshot.plan_status,
            review_round=snapshot.plan_review_round,
            max_review_rounds=snapshot.max_plan_review_rounds,
        ),
        action=action_label,
    )


def _spec_gates(snapshot: LifecycleSnapshot, *, action_label: str) -> tuple[GateSpec, ...]:
    return collect_spec_gate_specs(
        SpecState(status=snapshot.spec_status),
        action=action_label,
    )


def _conformance_gates(snapshot: LifecycleSnapshot, *, action_label: str) -> list[GateSpec]:
    conformance = snapshot.conformance
    gates: list[GateSpec] = []
    if conformance.status == "red":
        gates.append(
            _gate(
                "CONFORMANCE_BLOCKED",
                f"task conformance has blocking drift before {action_label}",
                "conformance",
                severity="red",
                checkpoint_type=conformance.last_checkpoint_type,
            )
        )
    if conformance.unresolved_warning_count > 0:
        gates.append(
            _gate(
                "CONFORMANCE_WARNING_UNRESOLVED",
                f"task conformance has unresolved warnings before {action_label}",
                "conformance",
                severity="yellow",
                checkpoint_type=conformance.last_checkpoint_type,
            )
        )
    for subtask in conformance.subtasks:
        if subtask.status == "red":
            gates.append(
                _gate(
                    "CONFORMANCE_BLOCKED",
                    f"subtask \x60{subtask.subtask_id}\x60 has blocking drift before {action_label}",
                    "conformance",
                    severity="red",
                    checkpoint_type=subtask.last_checkpoint_type,
                    subtask_id=subtask.subtask_id,
                )
            )
        if subtask.unresolved_warning_count > 0:
            gates.append(
                _gate(
                    "CONFORMANCE_WARNING_UNRESOLVED",
                    f"subtask \x60{subtask.subtask_id}\x60 has unresolved warnings before {action_label}",
                    "conformance",
                    severity="yellow",
                    checkpoint_type=subtask.last_checkpoint_type,
                    subtask_id=subtask.subtask_id,
                )
            )
    return list(dedupe_gate_specs(gates))


def _close_gates(snapshot: LifecycleSnapshot) -> list[GateSpec]:
    gates = list(_plan_gates(snapshot, action_label="close"))
    gates.extend(_conformance_gates(snapshot, action_label="close"))
    if snapshot.verify_status != "passed":
        gates.append(_gate("VERIFY_REQUIRED", "task must pass verify before close", "close"))
    if not snapshot.promotion.is_complete:
        gates.append(
            _gate(
                "PROMOTION_REQUIRED",
                "task requires promotion completion before close",
                "close",
            )
        )
    return list(dedupe_gate_specs(gates))


def _promotion_gates(snapshot: LifecycleSnapshot) -> list[GateSpec]:
    gates = list(_plan_gates(snapshot, action_label="promotion"))
    gates.extend(_spec_gates(snapshot, action_label="promotion"))
    gates.extend(_conformance_gates(snapshot, action_label="promotion"))
    if snapshot.verify_status != "passed":
        gates.append(_gate("VERIFY_REQUIRED", "task must pass verify before promotion", "promotion"))
    return list(dedupe_gate_specs(gates))


def _gate(
    code: str,
    message: str,
    source: str,
    *,
    severity: str | None = None,
    checkpoint_type: str | None = None,
    subtask_id: str | None = None,
) -> GateSpec:
    return GateSpec(
        code=code,
        message=message,
        source=source,
        severity=severity,
        checkpoint_type=checkpoint_type,
        subtask_id=subtask_id,
    )


def _allowed(
    snapshot: LifecycleSnapshot,
    action: LifecycleAction,
    next_phase: str | None,
    reason: str,
) -> TransitionDecision:
    return TransitionDecision(
        allowed=True,
        action=action,
        current_phase=snapshot.current_phase,
        next_phase=next_phase,
        gates=(),
        reason=reason,
    )


def _blocked(
    snapshot: LifecycleSnapshot,
    action: LifecycleAction,
    *gates: GateSpec,
    reason: str,
) -> TransitionDecision:
    return TransitionDecision(
        allowed=False,
        action=action,
        current_phase=snapshot.current_phase,
        next_phase=None,
        gates=dedupe_gate_specs(list(gates)),
        reason=reason,
    )


__all__ = ["HUMAN_GATED_ACTIONS", "evaluate_lifecycle_policy"]
