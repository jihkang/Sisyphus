from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path

from ..application.verification_evidence import (
    DEFAULT_EVIDENCE_GRAPH_PATH as DEFAULT_EVIDENCE_GRAPH_RELATIVE_PATH,
)
from .persistence.atomic_text import write_text_file


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
    write_text_file(path, json.dumps(dict(graph), indent=2, sort_keys=True) + "\n")
    return path


__all__ = [
    "DEFAULT_EVIDENCE_GRAPH_PATH",
    "evidence_graph_path",
    "read_evidence_graph",
    "write_evidence_graph",
]
