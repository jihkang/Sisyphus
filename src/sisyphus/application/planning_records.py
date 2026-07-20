from __future__ import annotations

from collections.abc import Iterable

from ..domain.gates import GateSpec
from ..domain.lifecycle import LifecycleAction, LifecycleSnapshot, TransitionDecision, evaluate_lifecycle_policy
from ..domain.planning.models import (
    PlanReviewState,
    SpecState,
    normalize_plan_status,
    normalize_spec_status,
)
from ..domain.planning.policy import collect_plan_gate_specs, collect_spec_gate_specs
from .ports.workflow import TaskRecord


def current_plan_status(task: TaskRecord) -> str:
    return normalize_plan_status(task.get("plan_status")).value


def current_spec_status(task: TaskRecord) -> str:
    return normalize_spec_status(task.get("spec_status")).value


def collect_plan_gate_records(
    task: TaskRecord,
    *,
    action: str,
    created_at: str,
) -> list[dict]:
    specs = collect_plan_gate_specs(
        PlanReviewState(
            status=normalize_plan_status(task.get("plan_status")),
            review_round=int(task.get("plan_review_round", 0)),
            max_review_rounds=int(task.get("max_plan_review_rounds", 3)),
        ),
        action=action,
    )
    return [gate_spec_to_record(spec, created_at=created_at) for spec in specs]


def collect_spec_gate_records(
    task: TaskRecord,
    *,
    action: str,
    created_at: str,
) -> list[dict]:
    specs = collect_spec_gate_specs(
        SpecState(status=normalize_spec_status(task.get("spec_status"))),
        action=action,
    )
    return [gate_spec_to_record(spec, created_at=created_at) for spec in specs]


def record_planning_lifecycle_transition(
    task: TaskRecord,
    action: LifecycleAction,
    *,
    gate_sources: Iterable[str],
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
    )
    decision = evaluate_lifecycle_policy(snapshot, action)
    sources = set(gate_sources)
    retained = [
        gate
        for gate in task.get("gates", [])
        if str(gate.get("source", "")).strip() not in sources
    ]
    task["gates"] = dedupe_gate_records(
        retained
        + [gate_spec_to_record(gate, created_at=created_at) for gate in decision.gates]
    )
    return decision


def gate_spec_to_record(gate: GateSpec, *, created_at: str) -> dict:
    return make_gate_record(
        gate.code,
        gate.message,
        gate.source,
        created_at=created_at,
        blocking=gate.blocking,
        severity=gate.severity,
        checkpoint_type=gate.checkpoint_type,
        subtask_id=gate.subtask_id,
    )


def make_gate_record(
    code: str,
    message: str,
    source: str,
    *,
    created_at: str,
    blocking: bool = True,
    severity: str | None = None,
    checkpoint_type: str | None = None,
    subtask_id: str | None = None,
) -> dict:
    record = {
        "code": code,
        "message": message,
        "blocking": blocking,
        "source": source,
        "created_at": created_at,
    }
    if severity:
        record["severity"] = severity
    if checkpoint_type:
        record["checkpoint_type"] = checkpoint_type
    if subtask_id:
        record["subtask_id"] = subtask_id
    return record


def dedupe_gate_records(gates: list[dict]) -> list[dict]:
    seen: set[tuple[object, object, object, object]] = set()
    result: list[dict] = []
    for gate in gates:
        identity = (
            gate.get("code", ""),
            gate.get("message", ""),
            gate.get("checkpoint_type"),
            gate.get("subtask_id"),
        )
        if identity in seen:
            continue
        seen.add(identity)
        result.append(gate)
    return result


def _optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


__all__ = [
    "collect_plan_gate_records",
    "collect_spec_gate_records",
    "current_plan_status",
    "current_spec_status",
    "dedupe_gate_records",
    "gate_spec_to_record",
    "make_gate_record",
    "record_planning_lifecycle_transition",
]
