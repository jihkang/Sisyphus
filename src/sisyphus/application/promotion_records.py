from __future__ import annotations

from ..domain.lifecycle import (
    ConformanceState,
    LifecycleAction,
    LifecycleSnapshot,
    TransitionDecision,
    evaluate_lifecycle_policy,
)
from ..domain.planning.models import normalize_plan_status, normalize_spec_status
from .planning_records import dedupe_gate_records, gate_spec_to_record
from .ports.workflow import TaskRecord


def record_promotion_lifecycle_transition(
    task: TaskRecord,
    action: LifecycleAction,
    conformance: ConformanceState,
    *,
    created_at: str,
) -> TransitionDecision:
    snapshot = LifecycleSnapshot(
        current_phase=_optional_text(task.get("workflow_phase")),
        closed=str(task.get("status") or "").strip().lower() == "closed" or bool(task.get("closed_at")),
        plan_status=normalize_plan_status(task.get("plan_status")),
        plan_review_round=int(task.get("plan_review_round", 0)),
        max_plan_review_rounds=int(task.get("max_plan_review_rounds", 3)),
        spec_status=normalize_spec_status(task.get("spec_status")),
        verify_status=str(task.get("verify_status") or ""),
        conformance=conformance,
    )
    decision = evaluate_lifecycle_policy(snapshot, action)
    replaced_sources = (
        {"lifecycle"}
        if action == LifecycleAction.RECORD_MERGED_PR
        else {"plan", "spec", "conformance", "promotion", "lifecycle"}
    )
    task["gates"] = dedupe_gate_records(
        [
            gate
            for gate in task.get("gates", [])
            if str(gate.get("source", "")).strip() not in replaced_sources
        ]
        + [gate_spec_to_record(gate, created_at=created_at) for gate in decision.gates]
    )
    return decision


def blocked_stage(decision: TransitionDecision) -> str:
    sources = {gate.source for gate in decision.gates}
    if "plan" in sources:
        return "plan_review"
    if "spec" in sources:
        return "spec"
    if "promotion" in sources:
        return "promotion"
    return "audit"


def blocked_phase(decision: TransitionDecision) -> str:
    sources = {gate.source for gate in decision.gates}
    if "plan" in sources:
        return "plan_in_review"
    if "spec" in sources:
        return "spec_in_review"
    if "promotion" in sources:
        return "promotion_pending"
    return decision.current_phase or "blocked"


def _optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


__all__ = [
    "blocked_phase",
    "blocked_stage",
    "record_promotion_lifecycle_transition",
]
