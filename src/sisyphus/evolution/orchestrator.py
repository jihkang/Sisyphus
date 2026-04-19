from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
import json

from .constraints import EvolutionConstraintResult, evaluate_evolution_constraints
from .dataset import EvolutionDataset, build_evolution_dataset
from .fitness import EvolutionFitnessResult, evaluate_evolution_fitness
from .harness import EvolutionHarnessPlan, plan_evolution_harness
from .report import EvolutionReport, build_evolution_report
from .runner import EvolutionRun, plan_evolution_run, utc_now
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
    dataset_builder: Callable[..., EvolutionDataset] = build_evolution_dataset,
    harness_planner: Callable[..., EvolutionHarnessPlan] = plan_evolution_harness,
    constraints_evaluator: Callable[..., EvolutionConstraintResult] = evaluate_evolution_constraints,
    fitness_evaluator: Callable[..., EvolutionFitnessResult] = evaluate_evolution_fitness,
    report_builder: Callable[..., EvolutionReport] = build_evolution_report,
) -> EvolutionExecutedRun:
    run = plan_evolution_run(
        repo_root,
        target_ids=target_ids,
        run_id=run_id,
        created_at=created_at,
    )
    run_dir = _create_run_dir(Path(run.repo_root), run.run_id)
    persisted_artifacts: list[str] = []
    _write_json(
        run_dir / "run.json",
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
        _write_json(
            run_dir / "dataset.json",
            {
                **asdict(dataset),
                "task_count": dataset.task_count,
                "event_count": dataset.event_count,
            },
        )
        persisted_artifacts.append("dataset.json")

        harness = harness_planner(run, dataset)
        _write_json(run_dir / "harness_plan.json", asdict(harness))
        persisted_artifacts.append("harness_plan.json")

        constraint_result = constraints_evaluator(harness)
        _write_json(run_dir / "constraints.json", asdict(constraint_result))
        persisted_artifacts.append("constraints.json")

        fitness_result = fitness_evaluator(harness, constraints=constraint_result)
        _write_json(run_dir / "fitness.json", asdict(fitness_result))
        persisted_artifacts.append("fitness.json")

        report = report_builder(
            run,
            dataset,
            harness,
            constraint_result=constraint_result,
            fitness_result=fitness_result,
        )
        (run_dir / "report.md").write_text(_render_report_markdown(report), encoding="utf-8")
        persisted_artifacts.append("report.md")

        return EvolutionExecutedRun(
            run=run,
            artifact_dir=str(run_dir),
            final_stage=EVOLUTION_STAGE_REPORT_BUILT,
            dataset=dataset,
            harness=harness,
            constraint_result=constraint_result,
            fitness_result=fitness_result,
            report=report,
        )
    except Exception as exc:
        failure_stage = _infer_failure_stage(dataset, harness, constraint_result, fitness_result)
        failure = EvolutionRunFailure(
            stage=failure_stage,
            error_type=type(exc).__name__,
            message=str(exc),
            failed_at=utc_now(),
            partial_artifacts=tuple(persisted_artifacts),
        )
        _write_json(run_dir / "failure.json", asdict(failure))
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


def _create_run_dir(repo_root: Path, run_id: str) -> Path:
    run_dir = repo_root / ".planning" / "evolution" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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
