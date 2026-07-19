from __future__ import annotations

from collections.abc import Mapping, Sequence

from .closeout_records import (
    collect_evidence_close_gate_records,
    evidence_required_for_close,
)
from .verification_evidence import (
    EVIDENCE_GRAPH_SCHEMA_VERSION,
    EVIDENCE_IMPORTANCE_HIGH,
    EVIDENCE_VERDICT_SUPPORTS,
    build_verification_evidence_graph,
)


def project_evidence_graph(
    task: Mapping[str, object],
    command_results: Sequence[Mapping[str, object]],
    *,
    generated_at: str,
    conformance_status: str,
    changeset_path: str | None,
    changeset_present: bool,
) -> dict[str, object]:
    return build_verification_evidence_graph(
        task,
        command_results,
        generated_at=generated_at,
        conformance_status=conformance_status,
        changeset_path=changeset_path,
        changeset_present=changeset_present,
    )


def summarize_evidence_graph(
    task: Mapping[str, object],
    graph: Mapping[str, object] | None,
    *,
    read_error: str | None = None,
    path: str,
) -> dict[str, object]:
    if read_error is not None:
        return {
            "status": "invalid",
            "path": path,
            "error": read_error,
            "curated_evidence": 0,
            "unsupported_claims": 0,
            "blocking_gaps": 0,
        }
    if graph is None:
        return {
            "status": "missing" if evidence_required_for_close(task) else "not_required",
            "path": path,
            "curated_evidence": 0,
            "unsupported_claims": 0,
            "blocking_gaps": 0,
        }

    evidence = _list_field(graph, "curated_evidence")
    unsupported_claims = _list_field(graph, "unsupported_claims")
    blocking_gaps = _list_field(graph, "blocking_gaps")
    high_supported = sum(
        1
        for item in evidence
        if isinstance(item, Mapping)
        and item.get("importance") == EVIDENCE_IMPORTANCE_HIGH
        and item.get("verdict") == EVIDENCE_VERDICT_SUPPORTS
    )
    status = "blocked" if blocking_gaps else "partial" if unsupported_claims else "complete"
    return {
        "status": status,
        "path": path,
        "curated_evidence": len(evidence),
        "high_supported": high_supported,
        "unsupported_claims": len(unsupported_claims),
        "blocking_gaps": len(blocking_gaps),
    }


def evidence_close_gates(
    task: Mapping[str, object],
    graph: Mapping[str, object] | None,
    *,
    read_error: str | None,
    created_at: str,
) -> list[dict]:
    if not evidence_required_for_close(task):
        return []
    return collect_evidence_close_gate_records(
        task,
        graph,
        read_error=read_error,
        created_at=created_at,
    )


def evidence_resource_payload(
    task: Mapping[str, object],
    graph: Mapping[str, object] | None,
    *,
    path: str,
) -> dict[str, object]:
    if graph is not None:
        return dict(graph)
    return {
        "schema_version": EVIDENCE_GRAPH_SCHEMA_VERSION,
        "task_id": task.get("id"),
        "status": "missing" if evidence_required_for_close(task) else "not_required",
        "path": path,
        "curated_evidence": [],
        "unsupported_claims": [],
        "blocking_gaps": [],
    }


def _list_field(graph: Mapping[str, object], key: str) -> list[object]:
    value = graph.get(key)
    return list(value) if isinstance(value, list) else []


__all__ = [
    "EVIDENCE_GRAPH_SCHEMA_VERSION",
    "evidence_close_gates",
    "evidence_required_for_close",
    "evidence_resource_payload",
    "project_evidence_graph",
    "summarize_evidence_graph",
]
