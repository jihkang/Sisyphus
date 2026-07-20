from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path

from ...application.closeout_records import (
    collect_evidence_close_gate_records,
    evidence_required_for_close,
)
from ...application.ports.clock import ClockPort
from ...application.ports.workflow import TaskRecord
from ...application.verification_evidence import DEFAULT_EVIDENCE_GRAPH_PATH
from ..artifacts import RepositoryArtifactStore
from ..config.loader import SisyphusConfig


class RepositoryCloseoutEvidenceAdapter:
    def __init__(
        self,
        repo_root: Path,
        config: SisyphusConfig,
        clock: ClockPort,
    ) -> None:
        self._artifacts = RepositoryArtifactStore(repo_root, config)
        self._clock = clock

    def collect_gates(self, task_id: str, task: TaskRecord) -> tuple[dict, ...]:
        if not evidence_required_for_close(task):
            return ()
        path = self._artifacts.resolve(task_id, DEFAULT_EVIDENCE_GRAPH_PATH)
        graph: Mapping[str, object] | None = None
        read_error: str | None = None
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError(f"evidence graph must be a JSON object: {path}")
                graph = payload
            except (json.JSONDecodeError, ValueError) as exc:
                read_error = str(exc)
        return tuple(
            collect_evidence_close_gate_records(
                task,
                graph,
                read_error=read_error,
                created_at=self._clock.now(),
            )
        )


__all__ = ["RepositoryCloseoutEvidenceAdapter"]
