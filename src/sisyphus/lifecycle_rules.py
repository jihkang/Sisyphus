from __future__ import annotations

from .conformance import collect_conformance_gates
from .gates import dedupe_gates, make_gate
from .lifecycle_state import LifecycleAction, TransitionResult
from .planning import PLAN_CHANGES_REQUESTED, collect_plan_gates, collect_spec_execution_gates, current_plan_status
from .promotion_state import (
    PROMOTION_STATUS_NOT_REQUIRED,
    PROMOTION_STATUS_RECORDED,
    promotion_summary,
)


HUMAN_GATED_ACTIONS = frozenset(
    {
        LifecycleAction.APPROVE_PLAN,
        LifecycleAction.FREEZE_SPEC,
        LifecycleAction.EXECUTE_PROMOTION,
        LifecycleAction.RECORD_MERGED_PR,
    }
)


def evaluate_transition(task: dict, action: LifecycleAction | str) -> TransitionResult:
    lifecycle_action = action if isinstance(action, LifecycleAction) else LifecycleAction(str(action))
    current_phase = _optional_phase(task)

    if _is_closed(task) and lifecycle_action != LifecycleAction.CLOSE:
        return _blocked(
            task,
            lifecycle_action,
            make_gate("TASK_CLOSED", "closed tasks do not accept lifecycle transitions", "lifecycle"),
            reason="Task is already closed.",
        )

    if lifecycle_action == LifecycleAction.APPROVE_PLAN:
        return _allowed(task, lifecycle_action, "spec_drafting", "Plan approval is a review-gated transition.")

    if lifecycle_action == LifecycleAction.REQUEST_PLAN_CHANGES:
        return _allowed(task, lifecycle_action, "plan_revision", "Plan changes can be requested by a reviewer.")

    if lifecycle_action == LifecycleAction.REVISE_PLAN:
        if current_plan_status(task) != PLAN_CHANGES_REQUESTED:
            return _blocked(
                task,
                lifecycle_action,
                make_gate("PLAN_REVISION_NOT_REQUESTED", "plan revision requires requested changes", "plan"),
                reason="Plan revision is only valid after review requests changes.",
            )
        return _allowed(task, lifecycle_action, "plan_in_review", "Plan revision resubmits the task for review.")

    if lifecycle_action == LifecycleAction.FREEZE_SPEC:
        gates = collect_plan_gates(task, action="spec freeze")
        if gates:
            return _blocked(task, lifecycle_action, *gates, reason="Spec cannot be frozen before plan approval.")
        return _allowed(task, lifecycle_action, "subtask_planning", "Spec freeze is allowed after plan approval.")

    if lifecycle_action == LifecycleAction.GENERATE_SUBTASKS:
        gates = _execution_readiness_gates(task, action="subtask generation", include_conformance=False)
        if gates:
            return _blocked(task, lifecycle_action, *gates, reason="Subtasks require an approved plan and frozen spec.")
        return _allowed(task, lifecycle_action, "execution", "Subtask generation is allowed.")

    if lifecycle_action == LifecycleAction.START_EXECUTION:
        gates = _execution_readiness_gates(task, action="execution")
        if gates:
            return _blocked(task, lifecycle_action, *gates, reason="Execution requires an approved, frozen, conformant task.")
        return _allowed(task, lifecycle_action, "execution", "Execution is allowed.")

    if lifecycle_action == LifecycleAction.VERIFY:
        gates = list(collect_plan_gates(task, action="verify"))
        gates.extend(collect_spec_execution_gates(task, action="verify"))
        gates.extend(collect_conformance_gates(task, action="verify"))
        if gates:
            return _blocked(task, lifecycle_action, *gates, reason="Verification is blocked by lifecycle gates.")
        return _allowed(task, lifecycle_action, "verified", "Verification may run.")

    if lifecycle_action == LifecycleAction.CLOSE:
        gates = _close_gates(task)
        if gates:
            return _blocked(task, lifecycle_action, *gates, reason="Close is blocked until lifecycle gates clear.")
        return _allowed(task, lifecycle_action, "closed", "Close is allowed.")

    if lifecycle_action == LifecycleAction.EXECUTE_PROMOTION:
        gates = _promotion_gates(task)
        if gates:
            return _blocked(task, lifecycle_action, *gates, reason="Promotion execution is blocked.")
        return _allowed(task, lifecycle_action, "promotion_pending", "Promotion execution is human-gated.")

    if lifecycle_action == LifecycleAction.RECORD_MERGED_PR:
        return _allowed(task, lifecycle_action, current_phase, "Recording a merged PR is human-gated.")

    return _blocked(
        task,
        lifecycle_action,
        make_gate("UNKNOWN_LIFECYCLE_ACTION", f"unsupported lifecycle action: {lifecycle_action}", "lifecycle"),
        reason="Unsupported lifecycle action.",
    )


def allowed_lifecycle_actions(task: dict) -> tuple[LifecycleAction, ...]:
    return tuple(action for action in LifecycleAction if evaluate_transition(task, action).allowed)


def forbidden_lifecycle_actions(task: dict) -> tuple[TransitionResult, ...]:
    return tuple(result for action in LifecycleAction if not (result := evaluate_transition(task, action)).allowed)


def _execution_readiness_gates(
    task: dict,
    *,
    action: str,
    include_conformance: bool = True,
) -> list[dict]:
    gates = list(collect_plan_gates(task, action=action))
    gates.extend(collect_spec_execution_gates(task, action=action))
    if include_conformance:
        gates.extend(collect_conformance_gates(task, action=action))
    return dedupe_gates(gates)


def _close_gates(task: dict) -> list[dict]:
    gates = list(collect_plan_gates(task, action="close"))
    gates.extend(collect_conformance_gates(task, action="close"))
    if task.get("verify_status") != "passed":
        gates.append(make_gate("VERIFY_REQUIRED", "task must pass verify before close", "close"))

    promotion = promotion_summary(task)
    if bool(promotion.get("required")) and promotion.get("status") not in {
        PROMOTION_STATUS_NOT_REQUIRED,
        PROMOTION_STATUS_RECORDED,
    }:
        gates.append(make_gate("PROMOTION_REQUIRED", "task requires promotion completion before close", "close"))
    return dedupe_gates(gates)


def _promotion_gates(task: dict) -> list[dict]:
    gates = list(collect_plan_gates(task, action="promotion"))
    gates.extend(collect_spec_execution_gates(task, action="promotion"))
    gates.extend(collect_conformance_gates(task, action="promotion"))
    if task.get("verify_status") != "passed":
        gates.append(make_gate("VERIFY_REQUIRED", "task must pass verify before promotion", "promotion"))
    return dedupe_gates(gates)


def _allowed(task: dict, action: LifecycleAction, next_phase: str | None, reason: str) -> TransitionResult:
    return TransitionResult(
        allowed=True,
        action=action,
        current_phase=_optional_phase(task),
        next_phase=next_phase,
        gates=(),
        reason=reason,
    )


def _blocked(task: dict, action: LifecycleAction, *gates: dict, reason: str) -> TransitionResult:
    return TransitionResult(
        allowed=False,
        action=action,
        current_phase=_optional_phase(task),
        next_phase=None,
        gates=tuple(dedupe_gates(list(gates))),
        reason=reason,
    )


def _optional_phase(task: dict) -> str | None:
    phase = str(task.get("workflow_phase") or "").strip()
    return phase or None


def _is_closed(task: dict) -> bool:
    return str(task.get("status") or "").strip().lower() == "closed" or bool(task.get("closed_at"))


__all__ = [
    "HUMAN_GATED_ACTIONS",
    "allowed_lifecycle_actions",
    "evaluate_transition",
    "forbidden_lifecycle_actions",
]
