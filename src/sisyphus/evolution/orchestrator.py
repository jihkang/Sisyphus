from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from ..application.ports.clock import ClockPort
from ..application.ports.evolution import EvolutionEventPort, EvolutionRunArtifactPort
from .constraints import EvolutionConstraintResult, evaluate_evolution_constraints
from .dataset import EvolutionDataset
from ..application.evolution_events import (
    EVOLUTION_EVENT_RUN_FAILED,
    EVOLUTION_EVENT_RUN_RECORDED,
)
from .fitness import EvolutionFitnessResult, evaluate_evolution_fitness
from .harness import EvolutionHarnessPlan, plan_evolution_harness
from .report import EvolutionReport, build_evolution_report
from .runner import EvolutionRun, plan_evolution_run
from .stages import EVOLUTION_STAGE_FAILED, EVOLUTION_STAGE_REPORT_BUILT


@dataclass(frozen=True, slots=True)
class EvolutionRunFailure:
    stage: str
    error_type: str
    message: str
    failed_at: str
    partial_artifacts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvolutionExecutedRun:
    run: EvolutionRun
    artifact_dir: str
    final_stage: str
    dataset: EvolutionDataset | None = None
    harness: EvolutionHarnessPlan | None = None
    constraint_result: EvolutionConstraintResult | None = None
    fitness_result: EvolutionFitnessResult | None = None
    report: EvolutionReport | None = None
    failure: EvolutionRunFailure | None = None


def execute_evolution_run(
    repo_root: Path,
    *,
    target_ids: Sequence[str] | None = None,
    task_ids: Sequence[str] | None = None,
    max_events: int = 50,
    run_id: str | None = None,
    created_at: str | None = None,
    run_store: EvolutionRunArtifactPort,
    events: EvolutionEventPort,
    clock: ClockPort,
    dataset_builder: Callable[..., EvolutionDataset] | None = None,
    harness_planner: Callable[..., EvolutionHarnessPlan] = plan_evolution_harness,
    constraints_evaluator: Callable[..., EvolutionConstraintResult] = evaluate_evolution_constraints,
    fitness_evaluator: Callable[..., EvolutionFitnessResult] = evaluate_evolution_fitness,
    report_builder: Callable[..., EvolutionReport] = build_evolution_report,
) -> EvolutionExecutedRun:
    if dataset_builder is None:
        raise ValueError("evolution execution requires an injected dataset builder")
    run = plan_evolution_run(
        repo_root,
        target_ids=target_ids,
        run_id=run_id,
        created_at=created_at or clock.now(),
    )
    run_dir = run_store.create_run(run.run_id)
    persisted_artifacts: list[str] = []
    run_store.append_json(
        run.run_id,
        "run.json",
        {
            "run": asdict(run),
            "artifact_dir": str(run_dir),
            "entrypoint": "execute_evolution_run",
            "write_scope": ".planning/evolution/runs/<run_id>/",
        },
    )
    persisted_artifacts.append("run.json")

    dataset: EvolutionDataset | None = None
    harness: EvolutionHarnessPlan | None = None
    constraint_result: EvolutionConstraintResult | None = None
    fitness_result: EvolutionFitnessResult | None = None
    report: EvolutionReport | None = None

    try:
        dataset = dataset_builder(Path(run.repo_root), task_ids=task_ids, max_events=max_events)
        run_store.append_json(
            run.run_id,
            "dataset.json",
            {
                **asdict(dataset),
                "task_count": dataset.task_count,
                "event_count": dataset.event_count,
            },
        )
        persisted_artifacts.append("dataset.json")

        harness = harness_planner(run, dataset)
        run_store.append_json(run.run_id, "harness_plan.json", asdict(harness))
        persisted_artifacts.append("harness_plan.json")

        constraint_result = constraints_evaluator(harness)
        run_store.append_json(run.run_id, "constraints.json", asdict(constraint_result))
        persisted_artifacts.append("constraints.json")

        fitness_result = fitness_evaluator(harness, constraints=constraint_result)
        run_store.append_json(run.run_id, "fitness.json", asdict(fitness_result))
        persisted_artifacts.append("fitness.json")

        report = report_builder(
            run,
            dataset,
            harness,
            constraint_result=constraint_result,
            fitness_result=fitness_result,
        )
        run_store.append_text(run.run_id, "report.md", _render_report_markdown(report))
        persisted_artifacts.append("report.md")

        result = EvolutionExecutedRun(
            run=run,
            artifact_dir=str(run_dir),
            final_stage=EVOLUTION_STAGE_REPORT_BUILT,
            dataset=dataset,
            harness=harness,
            constraint_result=constraint_result,
            fitness_result=fitness_result,
            report=report,
        )
        events.publish(
            event_type=EVOLUTION_EVENT_RUN_RECORDED,
            source_module="evolution.orchestrator",
            data={
                "run_id": run.run_id,
                "final_stage": result.final_stage,
                "artifact_dir": result.artifact_dir,
                "selection_mode": run.selection_mode,
                "target_ids": list(run.target_ids),
                "persisted_artifacts": list(persisted_artifacts),
            },
        )
        return result
    except Exception as exc:
        failure_stage = _infer_failure_stage(dataset, harness, constraint_result, fitness_result)
        failure = EvolutionRunFailure(
            stage=failure_stage,
            error_type=type(exc).__name__,
            message=str(exc),
            failed_at=clock.now(),
            partial_artifacts=tuple(persisted_artifacts),
        )
        run_store.append_json(run.run_id, "failure.json", asdict(failure))
        events.publish(
            event_type=EVOLUTION_EVENT_RUN_FAILED,
            source_module="evolution.orchestrator",
            data={
                "run_id": run.run_id,
                "final_stage": EVOLUTION_STAGE_FAILED,
                "artifact_dir": str(run_dir),
                "failure_stage": failure.stage,
                "error_type": failure.error_type,
                "message": failure.message,
                "persisted_artifacts": list(failure.partial_artifacts),
            },
        )
        raise EvolutionRunExecutionError(
            run=run,
            artifact_dir=str(run_dir),
            final_stage=EVOLUTION_STAGE_FAILED,
            dataset=dataset,
            harness=harness,
            constraint_result=constraint_result,
            fitness_result=fitness_result,
            report=report,
            failure=failure,
        ) from exc


class EvolutionRunExecutionError(RuntimeError):
    def __init__(
        self,
        *,
        run: EvolutionRun,
        artifact_dir: str,
        final_stage: str,
        dataset: EvolutionDataset | None,
        harness: EvolutionHarnessPlan | None,
        constraint_result: EvolutionConstraintResult | None,
        fitness_result: EvolutionFitnessResult | None,
        report: EvolutionReport | None,
        failure: EvolutionRunFailure,
    ) -> None:
        super().__init__(failure.message)
        self.result = EvolutionExecutedRun(
            run=run,
            artifact_dir=artifact_dir,
            final_stage=final_stage,
            dataset=dataset,
            harness=harness,
            constraint_result=constraint_result,
            fitness_result=fitness_result,
            report=report,
            failure=failure,
        )

def _render_report_markdown(report: EvolutionReport) -> str:
    lines = [
        "# Evolution Report",
        "",
        f"- Run ID: `{report.run_id}`",
        f"- Status: `{report.status}`",
        f"- Recommendation: `{report.recommendation}`",
        "",
        f"## {report.headline}",
        "",
        "### Summary",
    ]
    lines.extend(f"- {line}" for line in report.summary_lines)
    lines.extend(
        [
            "",
            "### Scope",
            f"- Repo Root: `{report.scope.repo_root}`",
            f"- Selection Mode: `{report.scope.selection_mode}`",
            f"- Isolation Mode: `{report.scope.isolation_mode}`",
            f"- Targets: {', '.join(report.scope.target_ids) or 'none'}",
            "",
            "### Dataset",
            f"- Tasks: `{report.dataset.task_count}`",
            f"- Events: `{report.dataset.event_count}`",
            f"- Selected Task IDs: {', '.join(report.dataset.selected_task_ids) or 'none'}",
            "",
            "### Comparison Placeholders",
        ]
    )
    lines.extend(
        f"- `{placeholder.placeholder_id}`: `{placeholder.status}` - {placeholder.detail}"
        for placeholder in report.comparison_placeholders
    )
    return "\n".join(lines) + "\n"


def _infer_failure_stage(
    dataset: EvolutionDataset | None,
    harness: EvolutionHarnessPlan | None,
    constraint_result: EvolutionConstraintResult | None,
    fitness_result: EvolutionFitnessResult | None,
) -> str:
    if fitness_result is not None:
        return EVOLUTION_STAGE_REPORT_BUILT
    if constraint_result is not None:
        return "fitness_evaluated"
    if harness is not None:
        return "constraints_evaluated"
    if dataset is not None:
        return "harness_planned"
    return "dataset_built"
