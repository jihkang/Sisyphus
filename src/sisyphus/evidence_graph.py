from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import json

from .application.closeout_records import (
    collect_evidence_close_gate_records,
    evidence_required_for_close as _evidence_required_for_close,
)
from .application.verification_evidence import (
    DEFAULT_EVIDENCE_GRAPH_PATH as DEFAULT_EVIDENCE_GRAPH_RELATIVE_PATH,
    EVIDENCE_GRAPH_SCHEMA_VERSION,
    EVIDENCE_IMPORTANCE_HIGH,
    EVIDENCE_IMPORTANCE_LOW,
    EVIDENCE_IMPORTANCE_MEDIUM,
    EVIDENCE_VERDICT_PARTIAL,
    EVIDENCE_VERDICT_SUPPORTS,
    build_verification_evidence_graph,
)
from .conformance import summarize_task_conformance
from .state import utc_now


DEFAULT_EVIDENCE_GRAPH_PATH = Path(DEFAULT_EVIDENCE_GRAPH_RELATIVE_PATH)


def evidence_graph_path(task_dir: Path) -> Path:
    return task_dir / DEFAULT_EVIDENCE_GRAPH_PATH


def read_evidence_graph(task_dir: Path) -> dict[str, object] | None:
    path = evidence_graph_path(task_dir)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"evidence graph must be a JSON object: {path}")
    return payload


def write_evidence_graph(task_dir: Path, graph: Mapping[str, object]) -> Path:
    path = evidence_graph_path(task_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(graph), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_evidence_graph(
    task: Mapping[str, object],
    task_dir: Path,
    command_results: Sequence[Mapping[str, object]],
    *,
    generated_at: str | None = None,
) -> dict[str, object]:
    generated = generated_at or utc_now()
    conformance = summarize_task_conformance(dict(task))
    conformance_status = str(conformance.get("status") or "unknown")
    docs = task.get("docs")
    changeset_path = str(docs.get("changeset") or "") if isinstance(docs, Mapping) else ""
    return build_verification_evidence_graph(
        task,
        command_results,
        generated_at=generated,
        conformance_status=conformance_status,
        changeset_path=changeset_path or None,
        changeset_present=bool(changeset_path and (task_dir / changeset_path).is_file()),
    )


def summarize_evidence_graph(task: Mapping[str, object], task_dir: Path) -> dict[str, object]:
    try:
        graph = read_evidence_graph(task_dir)
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "status": "invalid",
            "path": str(DEFAULT_EVIDENCE_GRAPH_PATH),
            "error": str(exc),
            "curated_evidence": 0,
            "unsupported_claims": 0,
            "blocking_gaps": 0,
        }
    if graph is None:
        return {
            "status": "missing" if evidence_required_for_close(task) else "not_required",
            "path": str(DEFAULT_EVIDENCE_GRAPH_PATH),
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
    status = "complete"
    if blocking_gaps:
        status = "blocked"
    elif unsupported_claims:
        status = "partial"
    return {
        "status": status,
        "path": str(DEFAULT_EVIDENCE_GRAPH_PATH),
        "curated_evidence": len(evidence),
        "high_supported": high_supported,
        "unsupported_claims": len(unsupported_claims),
        "blocking_gaps": len(blocking_gaps),
    }


def collect_evidence_close_gates(task: Mapping[str, object], task_dir: Path) -> list[dict]:
    if not _evidence_required_for_close(task):
        return []
    graph: dict[str, object] | None = None
    read_error: str | None = None
    try:
        graph = read_evidence_graph(task_dir)
    except (json.JSONDecodeError, ValueError) as exc:
        read_error = str(exc)
    return collect_evidence_close_gate_records(
        task,
        graph,
        read_error=read_error,
        created_at=utc_now(),
    )


def evidence_required_for_close(task: Mapping[str, object]) -> bool:
    return _evidence_required_for_close(task)


def evidence_resource_payload(task: Mapping[str, object], task_dir: Path) -> dict[str, object]:
    graph = read_evidence_graph(task_dir)
    if graph is not None:
        return graph
    return {
        "schema_version": EVIDENCE_GRAPH_SCHEMA_VERSION,
        "task_id": task.get("id"),
        "status": "missing" if evidence_required_for_close(task) else "not_required",
        "path": str(DEFAULT_EVIDENCE_GRAPH_PATH),
        "curated_evidence": [],
        "unsupported_claims": [],
        "blocking_gaps": [],
    }


def _list_field(graph: Mapping[str, object], key: str) -> list[object]:
    value = graph.get(key)
    return list(value) if isinstance(value, list) else []


__all__ = [
    "DEFAULT_EVIDENCE_GRAPH_PATH",
    "EVIDENCE_GRAPH_SCHEMA_VERSION",
    "build_evidence_graph",
    "collect_evidence_close_gates",
    "evidence_graph_path",
    "evidence_required_for_close",
    "evidence_resource_payload",
    "read_evidence_graph",
    "summarize_evidence_graph",
    "write_evidence_graph",
]
