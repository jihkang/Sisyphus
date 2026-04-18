from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from .dataset import EvolutionDataset
from .runner import EvolutionRun


EVOLUTION_EVALUATION_STATUS_PLANNED = "planned"
EVOLUTION_ISOLATION_MODE_TASK_WORKTREE_COPY = "task_worktree_copy"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class EvolutionPlannedMetrics:
    verify_pass_rate: float | None = None
    conformance_status: str | None = None
    drift_count: int | None = None
    unresolved_warning_count: int | None = None
    runtime_ms: int | None = None
    token_estimate: int | None = None
    operator_reviewability: str | None = None


@dataclass(frozen=True, slots=True)
class EvolutionEvaluationPlan:
    evaluation_id: str
    role: str
    label: str
    target_ids: tuple[str, ...]
    task_ids: tuple[str, ...]
    status: str
    metrics: EvolutionPlannedMetrics
    notes: str


@dataclass(frozen=True, slots=True)
class EvolutionHarnessPlan:
    run_id: str
    repo_root: str
    created_at: str
    isolation_mode: str
    mutates_live_task_state: bool
    requires_branch_snapshot: bool
    requires_task_worktree_copy: bool
    requires_result_capture: bool
    dataset_task_ids: tuple[str, ...]
    dataset_event_count: int
    baseline: EvolutionEvaluationPlan
    candidate: EvolutionEvaluationPlan
    notes: str


def plan_evolution_harness(
    run: EvolutionRun,
    dataset: EvolutionDataset,
    *,
    candidate_target_ids: Sequence[str] | None = None,
    candidate_label: str = "candidate",
    baseline_label: str = "baseline",
    created_at: str | None = None,
) -> EvolutionHarnessPlan:
    _validate_run_dataset_pair(run, dataset)
    candidate_ids = _resolve_candidate_target_ids(run.target_ids, candidate_target_ids)
    task_ids = dataset.selected_task_ids

    return EvolutionHarnessPlan(
        run_id=run.run_id,
        repo_root=run.repo_root,
        created_at=created_at or utc_now(),
        isolation_mode=EVOLUTION_ISOLATION_MODE_TASK_WORKTREE_COPY,
        mutates_live_task_state=False,
        requires_branch_snapshot=True,
        requires_task_worktree_copy=True,
        requires_result_capture=True,
        dataset_task_ids=task_ids,
        dataset_event_count=dataset.event_count,
        baseline=EvolutionEvaluationPlan(
            evaluation_id=f"{run.run_id}:baseline",
            role="baseline",
            label=baseline_label,
            target_ids=run.target_ids,
            task_ids=task_ids,
            status=EVOLUTION_EVALUATION_STATUS_PLANNED,
            metrics=EvolutionPlannedMetrics(),
            notes="planned baseline evaluation over the selected dataset; execution not implemented in this slice",
        ),
        candidate=EvolutionEvaluationPlan(
            evaluation_id=f"{run.run_id}:candidate",
            role="candidate",
            label=candidate_label,
            target_ids=candidate_ids,
            task_ids=task_ids,
            status=EVOLUTION_EVALUATION_STATUS_PLANNED,
            metrics=EvolutionPlannedMetrics(),
            notes="planned candidate evaluation over the selected dataset; execution not implemented in this slice",
        ),
        notes="harness planning only; branch snapshots, task/worktree copies, metrics population, and result execution remain future work",
    )


def _validate_run_dataset_pair(run: EvolutionRun, dataset: EvolutionDataset) -> None:
    if run.repo_root != dataset.repo_root:
        raise ValueError(
            "run and dataset must target the same repository root: "
            f"{run.repo_root} != {dataset.repo_root}"
        )
    if not dataset.selected_task_ids:
        raise ValueError("harness planning requires a dataset with at least one selected task")


def _resolve_candidate_target_ids(
    run_target_ids: tuple[str, ...],
    candidate_target_ids: Sequence[str] | None,
) -> tuple[str, ...]:
    if candidate_target_ids is None:
        return run_target_ids

    normalized_ids = [str(target_id).strip() for target_id in candidate_target_ids if str(target_id).strip()]
    if not normalized_ids:
        raise ValueError("candidate target narrowing requires at least one target id")

    allowed_ids = set(run_target_ids)
    requested_ids = set(normalized_ids)
    unknown_ids = sorted(requested_ids - allowed_ids)
    if unknown_ids:
        raise ValueError(f"candidate target ids are outside the run scope: {', '.join(unknown_ids)}")
    return tuple(target_id for target_id in run_target_ids if target_id in requested_ids)
