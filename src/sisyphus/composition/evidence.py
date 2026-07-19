from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path

from ..application.conformance_records import summarize_task_conformance
from ..application.evidence_queries import (
    EVIDENCE_GRAPH_SCHEMA_VERSION,
    evidence_close_gates,
    evidence_required_for_close,
    evidence_resource_payload as project_evidence_resource_payload,
    project_evidence_graph,
    summarize_evidence_graph as project_evidence_summary,
)
from ..infra.clock import SystemClock
from ..infra.evidence import (
    DEFAULT_EVIDENCE_GRAPH_PATH,
    evidence_graph_path,
    read_evidence_graph,
    write_evidence_graph,
)


def build_evidence_graph(
    task: Mapping[str, object],
    task_dir: Path,
    command_results: Sequence[Mapping[str, object]],
    *,
    generated_at: str | None = None,
) -> dict[str, object]:
    conformance = summarize_task_conformance(dict(task))
    docs = task.get("docs")
    changeset_path = str(docs.get("changeset") or "") if isinstance(docs, Mapping) else ""
    return project_evidence_graph(
        task,
        command_results,
        generated_at=generated_at or SystemClock().now(),
        conformance_status=str(conformance.get("status") or "unknown"),
        changeset_path=changeset_path or None,
        changeset_present=bool(changeset_path and (task_dir / changeset_path).is_file()),
    )


def summarize_evidence_graph(
    task: Mapping[str, object],
    task_dir: Path,
) -> dict[str, object]:
    graph: dict[str, object] | None = None
    read_error: str | None = None
    try:
        graph = read_evidence_graph(task_dir)
    except (json.JSONDecodeError, ValueError) as exc:
        read_error = str(exc)
    return project_evidence_summary(
        task,
        graph,
        read_error=read_error,
        path=str(DEFAULT_EVIDENCE_GRAPH_PATH),
    )


def collect_evidence_close_gates(
    task: Mapping[str, object],
    task_dir: Path,
) -> list[dict]:
    if not evidence_required_for_close(task):
        return []
    graph: dict[str, object] | None = None
    read_error: str | None = None
    try:
        graph = read_evidence_graph(task_dir)
    except (json.JSONDecodeError, ValueError) as exc:
        read_error = str(exc)
    return evidence_close_gates(
        task,
        graph,
        read_error=read_error,
        created_at=SystemClock().now(),
    )


def evidence_resource_payload(
    task: Mapping[str, object],
    task_dir: Path,
) -> dict[str, object]:
    return project_evidence_resource_payload(
        task,
        read_evidence_graph(task_dir),
        path=str(DEFAULT_EVIDENCE_GRAPH_PATH),
    )


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
