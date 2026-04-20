from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import uuid

from .artifacts import EvolutionArtifactRef
from .stages import EVOLUTION_RUN_STAGE_PLANNED, EvolutionRunStage, EvolutionStageFailure
from .targets import EvolutionTarget, resolve_evolution_targets


EVOLUTION_RUN_STATUS_PLANNED = EVOLUTION_RUN_STAGE_PLANNED


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_evolution_run_id() -> str:
    return f"EVR-{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True, slots=True)
class EvolutionRunRequest:
    repo_root: str
    target_ids: tuple[str, ...]
    run_id: str
    created_at: str
    notes: str


@dataclass(frozen=True, slots=True)
class EvolutionRun:
    request: EvolutionRunRequest
    run_id: str
    repo_root: str
    created_at: str
    stage: EvolutionRunStage
    status: str
    selection_mode: str
    target_ids: tuple[str, ...]
    targets: tuple[EvolutionTarget, ...]
    mutates_live_task_state: bool
    dataset_status: str
    notes: str


@dataclass(frozen=True, slots=True)
class EvolutionRunResult:
    run_id: str
    stage: EvolutionRunStage
    summary: str
    artifact_refs: tuple[EvolutionArtifactRef, ...] = ()
    failure: EvolutionStageFailure | None = None


@dataclass(frozen=True, slots=True)
class EvolutionPromotionCandidate:
    run_id: str
    candidate_id: str
    claim: str
    evidence: tuple[EvolutionArtifactRef, ...] = ()
    status: str = "planned_only"


@dataclass(frozen=True, slots=True)
class EvolutionInvalidationRecord:
    record_id: str
    run_id: str
    candidate_id: str
    reason: str
    affected_artifacts: tuple[EvolutionArtifactRef, ...] = ()
    evidence_refs: tuple[EvolutionArtifactRef, ...] = ()
    blocker_details: tuple[str, ...] = ()
    followup_task_id: str | None = None
    status: str = "planned_only"


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

    normalized_run_id = run_id or new_evolution_run_id()
    normalized_created_at = created_at or utc_now()
    normalized_target_ids = tuple(target_ids or ())
    request = EvolutionRunRequest(
        repo_root=str(resolved_repo_root),
        target_ids=normalized_target_ids,
        run_id=normalized_run_id,
        created_at=normalized_created_at,
        notes=(
            "planning-only request; executed harness runs, follow-up task handoff, "
            "and promotion recording remain future work"
        ),
    )

    selection_mode = "default" if not request.target_ids else "explicit"
    targets = resolve_evolution_targets(request.target_ids or None)
    if not targets:
        raise ValueError("evolution run requires at least one selected target")

    return EvolutionRun(
        request=request,
        run_id=normalized_run_id,
        repo_root=request.repo_root,
        created_at=request.created_at,
        stage=EVOLUTION_RUN_STAGE_PLANNED,
        status=EVOLUTION_RUN_STATUS_PLANNED,
        selection_mode=selection_mode,
        target_ids=tuple(target.target_id for target in targets),
        targets=targets,
        mutates_live_task_state=False,
        dataset_status="not_built",
        notes="skeleton run only; dataset, harness, scoring, and report execution are not implemented yet",
    )
