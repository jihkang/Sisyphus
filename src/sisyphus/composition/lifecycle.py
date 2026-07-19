from __future__ import annotations

from ..application.results.lifecycle import TransitionResult
from ..domain.lifecycle import HUMAN_GATED_ACTIONS, LifecycleAction, evaluate_lifecycle_policy
from ..infra.persistence.lifecycle_mapper import LifecycleRecordMapper


def evaluate_transition(task: dict, action: LifecycleAction | str) -> TransitionResult:
    lifecycle_action = action if isinstance(action, LifecycleAction) else LifecycleAction(str(action))
    snapshot = LifecycleRecordMapper.to_domain(task, action=lifecycle_action)
    decision = evaluate_lifecycle_policy(snapshot, lifecycle_action)
    return TransitionResult(
        allowed=decision.allowed,
        action=decision.action,
        current_phase=decision.current_phase,
        next_phase=decision.next_phase,
        gates=tuple(LifecycleRecordMapper.gate_to_record(gate) for gate in decision.gates),
        reason=decision.reason,
    )


def allowed_lifecycle_actions(task: dict) -> tuple[LifecycleAction, ...]:
    return tuple(action for action in LifecycleAction if evaluate_transition(task, action).allowed)


def forbidden_lifecycle_actions(task: dict) -> tuple[TransitionResult, ...]:
    return tuple(result for action in LifecycleAction if not (result := evaluate_transition(task, action)).allowed)


__all__ = [
    "HUMAN_GATED_ACTIONS",
    "allowed_lifecycle_actions",
    "evaluate_transition",
    "forbidden_lifecycle_actions",
]
