from __future__ import annotations

from ..application.action_space import (
    allowed_policy_actions_for,
    forbidden_policy_actions_for,
)
from .lifecycle import evaluate_transition


def allowed_policy_actions(task: dict) -> tuple[str, ...]:
    return allowed_policy_actions_for(task, evaluate_transition)


def forbidden_policy_actions(task: dict) -> tuple[dict[str, object], ...]:
    return forbidden_policy_actions_for(task, evaluate_transition)


__all__ = ["allowed_policy_actions", "forbidden_policy_actions"]
