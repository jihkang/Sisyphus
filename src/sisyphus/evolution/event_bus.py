from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ..bus import build_event_publisher
from ..config import SisyphusConfig, load_config
from ..events import new_event_envelope


EVOLUTION_EVENT_RUN_RECORDED = "evolution.run.recorded"
EVOLUTION_EVENT_RUN_FAILED = "evolution.run.failed"
EVOLUTION_EVENT_FOLLOWUP_REQUESTED = "evolution.followup.requested"
EVOLUTION_EVENT_EXECUTION_PROJECTED = "evolution.execution.projected"
EVOLUTION_EVENT_VERIFICATION_PROJECTED = "evolution.verification.projected"
EVOLUTION_EVENT_DECISION_RECORDED = "evolution.decision.recorded"


def publish_evolution_event(
    repo_root: Path,
    *,
    config: SisyphusConfig | None = None,
    event_type: str,
    source_module: str,
    data: Mapping[str, object] | None = None,
    source: Mapping[str, object] | None = None,
) -> None:
    resolved_repo_root = repo_root.resolve()
    resolved_config = config or load_config(resolved_repo_root)
    payload_source = {"module": source_module}
    if source:
        payload_source.update(source)
    build_event_publisher(resolved_repo_root, resolved_config).publish(
        new_event_envelope(
            event_type,
            source=payload_source,
            data=data or {},
        )
    )
