from __future__ import annotations

from collections.abc import Mapping

from ..domain.lifecycle import LifecycleAction, TransitionDecision, evaluate_lifecycle_policy
from .lifecycle_records import lifecycle_snapshot_from_record
from .planning_records import gate_spec_to_record, make_gate_record
from .ports.workflow import TaskRecord
from .verification_evidence import (
    EVIDENCE_IMPORTANCE_HIGH,
    EVIDENCE_VERDICT_MISSING,
    EVIDENCE_VERDICT_UNSUPPORTED,
)


def evaluate_closeout_lifecycle(
    task: TaskRecord,
    *,
    created_at: str,
) -> tuple[TransitionDecision, list[dict]]:
    decision = evaluate_lifecycle_policy(
        lifecycle_snapshot_from_record(task, action=LifecycleAction.CLOSE),
        LifecycleAction.CLOSE,
    )
    return decision, [
        gate_spec_to_record(gate, created_at=created_at) for gate in decision.gates
    ]


def collect_evidence_close_gate_records(
    task: Mapping[str, object],
    graph: Mapping[str, object] | None,
    *,
    read_error: str | None = None,
    created_at: str,
) -> list[dict]:
    if not evidence_required_for_close(task):
        return []
    if read_error is not None:
        return [
            make_gate_record(
                "EVIDENCE_GRAPH_INVALID",
                f"evidence graph is invalid: {read_error}",
                "evidence",
                created_at=created_at,
            )
        ]
    if graph is None:
        return [
            make_gate_record(
                "EVIDENCE_GRAPH_MISSING",
                "verified task is missing structured evidence graph",
                "evidence",
                created_at=created_at,
            )
        ]

    gates: list[dict] = []
    evidence = _list_field(graph, "curated_evidence")
    if any(
        isinstance(item, Mapping) and _is_blocking_unsupported_evidence(item)
        for item in evidence
    ):
        gates.append(
            make_gate_record(
                "EVIDENCE_UNSUPPORTED_HIGH_IMPORTANCE",
                "high-importance evidence contains unsupported or missing verdicts",
                "evidence",
                created_at=created_at,
            )
        )
    if _list_field(graph, "blocking_gaps"):
        gates.append(
            make_gate_record(
                "EVIDENCE_BLOCKING_GAP",
                "evidence graph contains blocking gaps",
                "evidence",
                created_at=created_at,
            )
        )
    return gates


def evidence_required_for_close(task: Mapping[str, object]) -> bool:
    meta = task.get("meta", {})
    if not isinstance(meta, Mapping):
        return False
    return task.get("verify_status") == "passed" and bool(meta.get("evidence_graph_required"))


def _is_blocking_unsupported_evidence(item: Mapping[str, object]) -> bool:
    return (
        item.get("importance") == EVIDENCE_IMPORTANCE_HIGH
        and item.get("verdict") in {EVIDENCE_VERDICT_UNSUPPORTED, EVIDENCE_VERDICT_MISSING}
        and bool(item.get("blocking", True))
    )


def _list_field(graph: Mapping[str, object], key: str) -> list[object]:
    value = graph.get(key)
    return list(value) if isinstance(value, list) else []


__all__ = [
    "collect_evidence_close_gate_records",
    "evaluate_closeout_lifecycle",
    "evidence_required_for_close",
]
