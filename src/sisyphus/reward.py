from __future__ import annotations

from dataclasses import dataclass

from .conformance import CONFORMANCE_GREEN, summarize_task_conformance
from .gates import blocking_gates
from .promotion_state import PROMOTION_STATUS_NOT_REQUIRED, PROMOTION_STATUS_RECORDED, promotion_summary


@dataclass(frozen=True, slots=True)
class TaskOutcomeFacts:
    task_id: str
    status: str
    verify_status: str
    conformance_status: str
    blocking_gate_count: int
    promotion_required: bool
    promotion_status: str | None


@dataclass(frozen=True, slots=True)
class RewardBreakdown:
    total: float
    task_closed: float
    verify_passed: float
    conformance_green: float
    promotion_complete: float
    gates_clear: float
    no_false_close: float
    penalties: dict[str, float]
    facts: TaskOutcomeFacts


def task_outcome_facts(task: dict) -> TaskOutcomeFacts:
    conformance = summarize_task_conformance(task)
    promotion = promotion_summary(task)
    gates = task.get("gates", [])
    if not isinstance(gates, list):
        gates = []
    return TaskOutcomeFacts(
        task_id=str(task.get("id") or ""),
        status=str(task.get("status") or ""),
        verify_status=str(task.get("verify_status") or ""),
        conformance_status=str(conformance.get("status") or ""),
        blocking_gate_count=len(blocking_gates(gates)),
        promotion_required=bool(promotion.get("required")),
        promotion_status=str(promotion.get("status")) if promotion.get("status") is not None else None,
    )


def score_task_outcome(task: dict) -> RewardBreakdown:
    facts = task_outcome_facts(task)
    promotion_done = (not facts.promotion_required) or facts.promotion_status in {
        PROMOTION_STATUS_NOT_REQUIRED,
        PROMOTION_STATUS_RECORDED,
    }

    task_closed = 1.0 if facts.status == "closed" else 0.0
    verify_passed = 0.8 if facts.verify_status == "passed" else 0.0
    conformance_green = 0.6 if facts.conformance_status == CONFORMANCE_GREEN else 0.0
    promotion_complete = 0.3 if promotion_done else 0.0
    gates_clear = 0.2 if facts.blocking_gate_count == 0 else 0.0

    penalties: dict[str, float] = {}
    if facts.status == "closed" and facts.verify_status != "passed":
        penalties["false_close"] = -1.0
    if facts.status == "closed" and facts.conformance_status != CONFORMANCE_GREEN:
        penalties["conformance_not_green_at_close"] = -0.6
    if facts.status == "closed" and not promotion_done:
        penalties["promotion_missing_at_close"] = -0.4
    if facts.status == "closed" and facts.blocking_gate_count > 0:
        penalties["blocking_gates_at_close"] = -0.3

    no_false_close = 0.3 if "false_close" not in penalties else 0.0
    total = round(
        task_closed
        + verify_passed
        + conformance_green
        + promotion_complete
        + gates_clear
        + no_false_close
        + sum(penalties.values()),
        3,
    )
    return RewardBreakdown(
        total=total,
        task_closed=task_closed,
        verify_passed=verify_passed,
        conformance_green=conformance_green,
        promotion_complete=promotion_complete,
        gates_clear=gates_clear,
        no_false_close=no_false_close,
        penalties=penalties,
        facts=facts,
    )


__all__ = ["RewardBreakdown", "TaskOutcomeFacts", "score_task_outcome", "task_outcome_facts"]
