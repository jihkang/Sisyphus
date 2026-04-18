from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import uuid

from .targets import EvolutionTarget, resolve_evolution_targets


EVOLUTION_RUN_STATUS_PLANNED = "planned"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_evolution_run_id() -> str:
    return f"EVR-{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True, slots=True)
class EvolutionRun:
    run_id: str
    repo_root: str
    created_at: str
    status: str
    selection_mode: str
    target_ids: tuple[str, ...]
    targets: tuple[EvolutionTarget, ...]
    mutates_live_task_state: bool
    dataset_status: str
    notes: str


def plan_evolution_run(
    repo_root: Path,
    *,
    target_ids: Sequence[str] | None = None,
    run_id: str | None = None,
    created_at: str | None = None,
) -> EvolutionRun:
    resolved_repo_root = repo_root.resolve()
    if not resolved_repo_root.exists():
        raise FileNotFoundError(f"repository root does not exist: {resolved_repo_root}")

    selection_mode = "default" if target_ids is None else "explicit"
    targets = resolve_evolution_targets(target_ids)
    if not targets:
        raise ValueError("evolution run requires at least one selected target")

    return EvolutionRun(
        run_id=run_id or new_evolution_run_id(),
        repo_root=str(resolved_repo_root),
        created_at=created_at or utc_now(),
        status=EVOLUTION_RUN_STATUS_PLANNED,
        selection_mode=selection_mode,
        target_ids=tuple(target.target_id for target in targets),
        targets=targets,
        mutates_live_task_state=False,
        dataset_status="not_built",
        notes="skeleton run only; dataset, harness, scoring, and report execution are not implemented yet",
    )
