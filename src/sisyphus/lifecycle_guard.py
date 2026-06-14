from __future__ import annotations

from collections.abc import Iterable

from .gates import dedupe_gates
from .lifecycle_rules import evaluate_transition
from .lifecycle_state import LifecycleAction, TransitionResult


DEFAULT_LIFECYCLE_GATE_SOURCES = frozenset({"lifecycle", "plan", "spec", "conformance", "close", "promotion"})


def record_lifecycle_transition(
    task: dict,
    action: LifecycleAction | str,
    *,
    gate_sources: Iterable[str] | None = None,
) -> TransitionResult:
    transition = evaluate_transition(task, action)
    sources = set(gate_sources or DEFAULT_LIFECYCLE_GATE_SOURCES)
    task["gates"] = dedupe_gates(
        [
            gate
            for gate in task.get("gates", [])
            if str(gate.get("source", "")).strip() not in sources
        ] + list(transition.gates)
    )
    return transition


def blocked_stage_for_transition(transition: TransitionResult) -> str:
    sources = {str(gate.get("source", "")).strip() for gate in transition.gates}
    if "plan" in sources:
        return "plan_review"
    if "spec" in sources:
        return "spec"
    if "promotion" in sources:
        return "promotion"
    return "audit"


def blocked_phase_for_transition(transition: TransitionResult) -> str:
    sources = {str(gate.get("source", "")).strip() for gate in transition.gates}
    if "plan" in sources:
        return "plan_in_review"
    if "spec" in sources:
        return "spec_in_review"
    if "promotion" in sources:
        return "promotion_pending"
    return transition.current_phase or "blocked"


__all__ = [
    "blocked_phase_for_transition",
    "blocked_stage_for_transition",
    "record_lifecycle_transition",
]
