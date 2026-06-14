from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .conformance import CONFORMANCE_GREEN, summarize_task_conformance
from .evidence_graph import summarize_evidence_graph
from .gates import blocking_gates
from .promotion_state import PROMOTION_STATUS_NOT_REQUIRED, PROMOTION_STATUS_RECORDED, promotion_summary


REWARD_METRIC_TASK_CLOSED = "task_closed"
REWARD_METRIC_VERIFY_PASSED = "verify_passed"
REWARD_METRIC_CONFORMANCE_GREEN = "conformance_green"
REWARD_METRIC_PROMOTION_COMPLETE = "promotion_complete"
REWARD_METRIC_EVIDENCE_COMPLETE = "evidence_complete"
REWARD_METRIC_GATES_CLEAR = "gates_clear"
REWARD_METRIC_NO_FALSE_CLOSE = "no_false_close"
REWARD_METRIC_ACTION_EFFICIENCY = "action_efficiency"
REWARD_METRIC_TOTAL = "reward_total"

REWARD_METRIC_NAMES = (
    REWARD_METRIC_TASK_CLOSED,
    REWARD_METRIC_VERIFY_PASSED,
    REWARD_METRIC_CONFORMANCE_GREEN,
    REWARD_METRIC_PROMOTION_COMPLETE,
    REWARD_METRIC_EVIDENCE_COMPLETE,
    REWARD_METRIC_GATES_CLEAR,
    REWARD_METRIC_NO_FALSE_CLOSE,
    REWARD_METRIC_ACTION_EFFICIENCY,
    REWARD_METRIC_TOTAL,
)


@dataclass(frozen=True, slots=True)
class TaskOutcomeFacts:
    task_id: str
    status: str
    verify_status: str
    conformance_status: str
    blocking_gate_count: int
    promotion_required: bool
    promotion_status: str | None
    evidence_status: str = "unknown"
    evidence_complete: bool = False
    curated_evidence_count: int = 0
    unsupported_claim_count: int = 0
    blocking_evidence_gap_count: int = 0
    action_count: int = 0
    excessive_action_count: bool = False
    false_close: bool = False


@dataclass(frozen=True, slots=True)
class RewardBreakdown:
    total: float
    task_closed: float
    verify_passed: float
    conformance_green: float
    promotion_complete: float
    evidence_complete: float
    gates_clear: float
    no_false_close: float
    action_efficiency: float
    penalties: dict[str, float]
    facts: TaskOutcomeFacts


def task_outcome_facts(
    task: dict,
    task_dir: Path | None = None,
    *,
    episode_steps: list[dict[str, object]] | None = None,
    max_action_count: int = 50,
) -> TaskOutcomeFacts:
    conformance = summarize_task_conformance(task)
    promotion = promotion_summary(task)
    gates = task.get("gates", [])
    if not isinstance(gates, list):
        gates = []
    evidence = _evidence_facts(task, task_dir)
    action_count = _action_count(episode_steps or [])
    status = str(task.get("status") or "")
    verify_status = str(task.get("verify_status") or "")
    return TaskOutcomeFacts(
        task_id=str(task.get("id") or ""),
        status=status,
        verify_status=verify_status,
        conformance_status=str(conformance.get("status") or ""),
        blocking_gate_count=len(blocking_gates(gates)),
        promotion_required=bool(promotion.get("required")),
        promotion_status=str(promotion.get("status")) if promotion.get("status") is not None else None,
        evidence_status=evidence["status"],
        evidence_complete=evidence["complete"],
        curated_evidence_count=evidence["curated_evidence"],
        unsupported_claim_count=evidence["unsupported_claims"],
        blocking_evidence_gap_count=evidence["blocking_gaps"],
        action_count=action_count,
        excessive_action_count=action_count > max(max_action_count, 0),
        false_close=status == "closed" and verify_status != "passed",
    )


def score_task_outcome(
    task: dict,
    task_dir: Path | None = None,
    *,
    episode_steps: list[dict[str, object]] | None = None,
    max_action_count: int = 50,
) -> RewardBreakdown:
    facts = task_outcome_facts(
        task,
        task_dir,
        episode_steps=episode_steps,
        max_action_count=max_action_count,
    )
    promotion_done = (not facts.promotion_required) or facts.promotion_status in {
        PROMOTION_STATUS_NOT_REQUIRED,
        PROMOTION_STATUS_RECORDED,
    }

    task_closed = 1.0 if facts.status == "closed" else 0.0
    verify_passed = 0.8 if facts.verify_status == "passed" else 0.0
    conformance_green = 0.6 if facts.conformance_status == CONFORMANCE_GREEN else 0.0
    promotion_complete = 0.3 if promotion_done else 0.0
    evidence_complete = 0.3 if facts.evidence_complete else 0.0
    gates_clear = 0.2 if facts.blocking_gate_count == 0 else 0.0
    action_efficiency = 0.2 if not facts.excessive_action_count else 0.0

    penalties: dict[str, float] = {}
    if facts.status == "closed" and facts.verify_status != "passed":
        penalties["false_close"] = -1.0
    if facts.conformance_status == "red":
        penalties["conformance_red"] = -0.6
    elif facts.status == "closed" and facts.conformance_status != CONFORMANCE_GREEN:
        penalties["conformance_not_green_at_close"] = -0.6
    if facts.status == "closed" and not promotion_done:
        penalties["promotion_missing_at_close"] = -0.4
    if facts.status == "closed" and facts.blocking_gate_count > 0:
        penalties["blocking_gates_at_close"] = -0.3
    if facts.evidence_status in {"missing", "invalid"}:
        penalties["missing_evidence"] = -0.2
    if facts.unsupported_claim_count or facts.blocking_evidence_gap_count:
        penalties["unsupported_evidence"] = -0.5
    if facts.excessive_action_count:
        penalties["excessive_action_count"] = -0.3

    no_false_close = 0.3 if "false_close" not in penalties else 0.0
    total = round(
        task_closed
        + verify_passed
        + conformance_green
        + promotion_complete
        + evidence_complete
        + gates_clear
        + no_false_close
        + action_efficiency
        + sum(penalties.values()),
        3,
    )
    return RewardBreakdown(
        total=total,
        task_closed=task_closed,
        verify_passed=verify_passed,
        conformance_green=conformance_green,
        promotion_complete=promotion_complete,
        evidence_complete=evidence_complete,
        gates_clear=gates_clear,
        no_false_close=no_false_close,
        action_efficiency=action_efficiency,
        penalties=penalties,
        facts=facts,
    )


def reward_breakdown_metrics(reward: RewardBreakdown) -> dict[str, float]:
    return {
        REWARD_METRIC_TASK_CLOSED: reward.task_closed,
        REWARD_METRIC_VERIFY_PASSED: reward.verify_passed,
        REWARD_METRIC_CONFORMANCE_GREEN: reward.conformance_green,
        REWARD_METRIC_PROMOTION_COMPLETE: reward.promotion_complete,
        REWARD_METRIC_EVIDENCE_COMPLETE: reward.evidence_complete,
        REWARD_METRIC_GATES_CLEAR: reward.gates_clear,
        REWARD_METRIC_NO_FALSE_CLOSE: reward.no_false_close,
        REWARD_METRIC_ACTION_EFFICIENCY: reward.action_efficiency,
        REWARD_METRIC_TOTAL: reward.total,
    }


def _evidence_facts(task: dict, task_dir: Path | None) -> dict[str, object]:
    if task_dir is None:
        return {
            "status": "unknown",
            "complete": False,
            "curated_evidence": 0,
            "unsupported_claims": 0,
            "blocking_gaps": 0,
        }
    summary = summarize_evidence_graph(task, task_dir)
    status = str(summary.get("status") or "unknown")
    return {
        "status": status,
        "complete": status in {"complete", "not_required"},
        "curated_evidence": _int_value(summary.get("curated_evidence")),
        "unsupported_claims": _int_value(summary.get("unsupported_claims")),
        "blocking_gaps": _int_value(summary.get("blocking_gaps")),
    }


def _action_count(episode_steps: list[dict[str, object]]) -> int:
    count = 0
    for step in episode_steps:
        action = step.get("action") if isinstance(step, dict) else None
        if isinstance(action, dict) and action.get("name"):
            count += 1
    return count


def _int_value(value: object) -> int:
    return value if isinstance(value, int) else 0


__all__ = [
    "REWARD_METRIC_ACTION_EFFICIENCY",
    "REWARD_METRIC_CONFORMANCE_GREEN",
    "REWARD_METRIC_EVIDENCE_COMPLETE",
    "REWARD_METRIC_GATES_CLEAR",
    "REWARD_METRIC_NAMES",
    "REWARD_METRIC_NO_FALSE_CLOSE",
    "REWARD_METRIC_PROMOTION_COMPLETE",
    "REWARD_METRIC_TASK_CLOSED",
    "REWARD_METRIC_TOTAL",
    "REWARD_METRIC_VERIFY_PASSED",
    "RewardBreakdown",
    "TaskOutcomeFacts",
    "reward_breakdown_metrics",
    "score_task_outcome",
    "task_outcome_facts",
]
