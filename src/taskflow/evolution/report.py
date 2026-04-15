from __future__ import annotations

from dataclasses import dataclass

from .constraints import EvolutionConstraintResult
from .dataset import EvolutionDataset
from .fitness import EvolutionFitnessResult
from .harness import EvolutionHarnessPlan, EvolutionPlannedMetrics
from .runner import EvolutionRun
from ..utils import utc_now


EVOLUTION_REPORT_STATUS_PLANNED = "planned"
EVOLUTION_REPORT_STATUS_READY_FOR_REVIEW = "ready_for_review"
EVOLUTION_REPORT_STATUS_REJECTED = "rejected"

EVOLUTION_REPORT_PLACEHOLDER_STATUS_AVAILABLE = "available"
EVOLUTION_REPORT_PLACEHOLDER_STATUS_PENDING = "pending"


@dataclass(frozen=True, slots=True)
class EvolutionReportScope:
    repo_root: str
    selection_mode: str
    target_ids: tuple[str, ...]
    target_titles: tuple[str, ...]
    isolation_mode: str
    mutates_live_task_state: bool
    requires_branch_snapshot: bool
    requires_task_worktree_copy: bool
    requires_result_capture: bool


@dataclass(frozen=True, slots=True)
class EvolutionReportDatasetSummary:
    generated_at: str
    task_count: int
    event_count: int
    selected_task_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvolutionReportEvaluationSummary:
    evaluation_id: str
    role: str
    label: str
    status: str
    target_ids: tuple[str, ...]
    task_ids: tuple[str, ...]
    metrics: EvolutionPlannedMetrics
    metric_summary: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvolutionComparisonPlaceholder:
    placeholder_id: str
    title: str
    status: str
    detail: str


@dataclass(frozen=True, slots=True)
class EvolutionReport:
    run_id: str
    generated_at: str
    status: str
    headline: str
    summary_lines: tuple[str, ...]
    recommendation: str
    scope: EvolutionReportScope
    dataset: EvolutionReportDatasetSummary
    baseline: EvolutionReportEvaluationSummary
    candidate: EvolutionReportEvaluationSummary
    constraint_result: EvolutionConstraintResult | None
    fitness_result: EvolutionFitnessResult | None
    comparison_placeholders: tuple[EvolutionComparisonPlaceholder, ...]


def build_evolution_report(
    run: EvolutionRun,
    dataset: EvolutionDataset,
    harness: EvolutionHarnessPlan,
    *,
    constraint_result: EvolutionConstraintResult | None = None,
    fitness_result: EvolutionFitnessResult | None = None,
    generated_at: str | None = None,
) -> EvolutionReport:
    _validate_report_inputs(run, dataset, harness)
    status, headline, recommendation = _report_state(constraint_result, fitness_result)
    comparison_placeholders = _build_placeholders(constraint_result, fitness_result)

    return EvolutionReport(
        run_id=run.run_id,
        generated_at=generated_at or utc_now(),
        status=status,
        headline=headline,
        summary_lines=_build_summary_lines(run, dataset, harness, constraint_result, fitness_result),
        recommendation=recommendation,
        scope=EvolutionReportScope(
            repo_root=run.repo_root,
            selection_mode=run.selection_mode,
            target_ids=run.target_ids,
            target_titles=tuple(target.title for target in run.targets),
            isolation_mode=harness.isolation_mode,
            mutates_live_task_state=harness.mutates_live_task_state,
            requires_branch_snapshot=harness.requires_branch_snapshot,
            requires_task_worktree_copy=harness.requires_task_worktree_copy,
            requires_result_capture=harness.requires_result_capture,
        ),
        dataset=EvolutionReportDatasetSummary(
            generated_at=dataset.generated_at,
            task_count=dataset.task_count,
            event_count=dataset.event_count,
            selected_task_ids=dataset.selected_task_ids,
        ),
        baseline=_build_evaluation_summary(harness.baseline),
        candidate=_build_evaluation_summary(harness.candidate),
        constraint_result=constraint_result,
        fitness_result=fitness_result,
        comparison_placeholders=comparison_placeholders,
    )


def _validate_report_inputs(run: EvolutionRun, dataset: EvolutionDataset, harness: EvolutionHarnessPlan) -> None:
    if run.repo_root != dataset.repo_root or run.repo_root != harness.repo_root:
        raise ValueError("run, dataset, and harness must target the same repository root")
    if run.run_id != harness.run_id:
        raise ValueError("run and harness must share the same run id")
    if dataset.selected_task_ids != harness.dataset_task_ids:
        raise ValueError("dataset and harness must use the same selected task ids")


def _report_state(
    constraint_result: EvolutionConstraintResult | None,
    fitness_result: EvolutionFitnessResult | None,
) -> tuple[str, str, str]:
    if constraint_result is not None and constraint_result.accepted is False:
        return (
            EVOLUTION_REPORT_STATUS_REJECTED,
            "Candidate failed hard guards and should not advance.",
            "reject_candidate",
        )
    if fitness_result is not None and fitness_result.status == "scored":
        return (
            EVOLUTION_REPORT_STATUS_READY_FOR_REVIEW,
            "Candidate produced a reviewable comparison against the current baseline.",
            "review_candidate",
        )
    return (
        EVOLUTION_REPORT_STATUS_PLANNED,
        "Evolution run is planned and awaiting executed comparison data.",
        "await_execution",
    )


def _build_summary_lines(
    run: EvolutionRun,
    dataset: EvolutionDataset,
    harness: EvolutionHarnessPlan,
    constraint_result: EvolutionConstraintResult | None,
    fitness_result: EvolutionFitnessResult | None,
) -> tuple[str, ...]:
    lines = [
        f"Targets: {len(run.target_ids)} selected across {dataset.task_count} tasks and {dataset.event_count} events.",
        f"Isolation: {harness.isolation_mode}; live task state mutation={harness.mutates_live_task_state}.",
    ]
    if constraint_result is None:
        lines.append("Hard guards: pending because no guard evaluation has been attached yet.")
    else:
        lines.append(
            "Hard guards: "
            f"{constraint_result.status} with {constraint_result.blocking_failure_count} blocking failures "
            f"and {constraint_result.pending_guard_count} pending checks."
        )
    if fitness_result is None or fitness_result.score_delta is None:
        lines.append("Fitness: awaiting comparable baseline and candidate metrics.")
    else:
        lines.append(
            "Fitness: "
            f"baseline {fitness_result.baseline_score:.2f}, candidate {fitness_result.candidate_score:.2f}, "
            f"delta {fitness_result.score_delta:+.2f}."
        )
    return tuple(lines)


def _build_evaluation_summary(evaluation) -> EvolutionReportEvaluationSummary:
    return EvolutionReportEvaluationSummary(
        evaluation_id=evaluation.evaluation_id,
        role=evaluation.role,
        label=evaluation.label,
        status=evaluation.status,
        target_ids=evaluation.target_ids,
        task_ids=evaluation.task_ids,
        metrics=evaluation.metrics,
        metric_summary=_metric_summary_lines(evaluation.metrics),
    )


def _metric_summary_lines(metrics: EvolutionPlannedMetrics) -> tuple[str, ...]:
    return (
        f"verify pass rate: {_format_percentage(metrics.verify_pass_rate)}",
        f"conformance status: {_format_text(metrics.conformance_status)}",
        f"drift count: {_format_integer(metrics.drift_count)}",
        f"unresolved warnings: {_format_integer(metrics.unresolved_warning_count)}",
        f"runtime: {_format_runtime(metrics.runtime_ms)}",
        f"token estimate: {_format_integer(metrics.token_estimate)}",
        f"operator reviewability: {_format_text(metrics.operator_reviewability)}",
    )


def _build_placeholders(
    constraint_result: EvolutionConstraintResult | None,
    fitness_result: EvolutionFitnessResult | None,
) -> tuple[EvolutionComparisonPlaceholder, ...]:
    return (
        EvolutionComparisonPlaceholder(
            placeholder_id="guard-summary",
            title="Guard Summary",
            status=EVOLUTION_REPORT_PLACEHOLDER_STATUS_AVAILABLE if constraint_result is not None else EVOLUTION_REPORT_PLACEHOLDER_STATUS_PENDING,
            detail=(
                "hard guard results are attached and ready for rendering"
                if constraint_result is not None
                else "hard guard results will populate once constraint evaluation runs"
            ),
        ),
        EvolutionComparisonPlaceholder(
            placeholder_id="candidate-comparison",
            title="Baseline vs Candidate Comparison",
            status=(
                EVOLUTION_REPORT_PLACEHOLDER_STATUS_AVAILABLE
                if fitness_result is not None and fitness_result.score_delta is not None
                else EVOLUTION_REPORT_PLACEHOLDER_STATUS_PENDING
            ),
            detail=(
                "fitness comparison is attached and ready for rendering"
                if fitness_result is not None and fitness_result.score_delta is not None
                else "comparison remains pending until both baseline and candidate metrics are scored"
            ),
        ),
        EvolutionComparisonPlaceholder(
            placeholder_id="branch-materialization",
            title="Branch Materialization",
            status=EVOLUTION_REPORT_PLACEHOLDER_STATUS_PENDING,
            detail=_branch_materialization_detail(constraint_result, fitness_result),
        ),
    )


def _branch_materialization_detail(
    constraint_result: EvolutionConstraintResult | None,
    fitness_result: EvolutionFitnessResult | None,
) -> str:
    if constraint_result is not None and constraint_result.accepted is False:
        return "branch proposal remains blocked because the candidate failed hard guards"
    if (
        constraint_result is not None
        and constraint_result.accepted is True
        and fitness_result is not None
        and fitness_result.status == "scored"
    ):
        return "candidate is eligible for a future approval/branch flow once that surface is implemented"
    return "branch proposal metadata remains future work until execution, scoring, and approval flows are complete"


def _format_percentage(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def _format_text(value: object | None) -> str:
    if value in (None, ""):
        return "n/a"
    return str(value)


def _format_integer(value: int | None) -> str:
    if value is None:
        return "n/a"
    return str(value)


def _format_runtime(value: int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value}ms"
