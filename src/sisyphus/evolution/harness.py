from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
import json
import subprocess
from time import perf_counter

from ..conformance import CONFORMANCE_GREEN, CONFORMANCE_RED, CONFORMANCE_YELLOW, normalize_conformance_status
from ..utils import optional_str

from .dataset import EvolutionDataset
from .materialization import (
    EVOLUTION_MATERIALIZATION_STATUS_FAILED,
    EvolutionMaterialization,
    EvolutionMaterializationError,
    materialize_evolution_evaluation,
    ordered_target_source_paths,
)
from .runner import EvolutionRun


EVOLUTION_EVALUATION_STATUS_PLANNED = "planned"
EVOLUTION_EVALUATION_STATUS_COMPLETED = "completed"
EVOLUTION_EVALUATION_STATUS_FAILED = "failed"
EVOLUTION_ISOLATION_MODE_TASK_WORKTREE_COPY = "task_worktree_copy"
EVOLUTION_EVALUATION_EXECUTION_MODE_SUMMARY = "summary"
EVOLUTION_EVALUATION_EXECUTION_MODE_SISYPHUS_TASK = "sisyphus_task"
EVOLUTION_EVALUATION_EXECUTION_MODE_WORKTREE_HARNESS = "worktree_harness"
EVOLUTION_OPERATOR_REVIEWABILITY_HIGH = "high"
EVOLUTION_OPERATOR_REVIEWABILITY_MEDIUM = "medium"
EVOLUTION_OPERATOR_REVIEWABILITY_LOW = "low"
EVOLUTION_OPERATOR_REVIEWABILITY_BLOCKED = "blocked"


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
class EvolutionEvaluationEvidence:
    mode: str
    detail: str
    task_id: str | None = None
    branch: str | None = None
    worktree_path: str | None = None
    provider: str | None = None
    agent_id: str | None = None
    task_status: str | None = None
    plan_status: str | None = None
    spec_status: str | None = None
    workflow_phase: str | None = None
    exit_code: int | None = None
    materialization_status: str | None = None
    materialization_manifest_path: str | None = None
    materialization_snapshot_root: str | None = None
    materialized_target_ids: tuple[str, ...] = ()
    materialized_file_paths: tuple[str, ...] = ()
    execution_receipt_path: str | None = None
    command_count: int = 0
    passed_command_count: int = 0


@dataclass(frozen=True, slots=True)
class EvolutionSisyphusEvaluationRequest:
    title: str
    message: str
    instruction: str | None = None
    task_type: str = "feature"
    slug: str | None = None
    agent_id: str = "evolution-evaluation"
    role: str = "worker"
    provider: str = "codex"
    owned_paths: tuple[str, ...] = ()
    provider_args: tuple[str, ...] = ()
    source_context: dict[str, object] | None = None
    auto_execute: bool = False
    plan_reviewer: str = "evolution-harness"
    plan_review_notes: str | None = None
    spec_reviewer: str = "evolution-harness"
    spec_review_notes: str | None = None


@dataclass(frozen=True, slots=True)
class EvolutionEvaluationOutcome:
    metrics: EvolutionPlannedMetrics
    evidence: EvolutionEvaluationEvidence | None = None


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
    evidence: EvolutionEvaluationEvidence | None = None


@dataclass(frozen=True, slots=True)
class EvolutionWorktreeCommand:
    source_task_id: str
    source: str
    original_command: str
    normalized_command: str


@dataclass(frozen=True, slots=True)
class EvolutionWorktreeCommandResult:
    source_task_id: str
    source: str
    original_command: str
    normalized_command: str
    status: str
    exit_code: int
    runtime_ms: int
    stdout_path: str
    stderr_path: str
    output_excerpt: str | None


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


EvolutionEvaluationExecutor = Callable[
    [EvolutionEvaluationPlan, EvolutionDataset],
    EvolutionEvaluationOutcome | EvolutionPlannedMetrics,
]


class EvolutionEvaluationExecutionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        metrics: EvolutionPlannedMetrics | None = None,
        evidence: EvolutionEvaluationEvidence | None = None,
    ) -> None:
        super().__init__(message)
        self.metrics = metrics
        self.evidence = evidence


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
            notes="planned baseline evaluation over the selected dataset",
        ),
        candidate=EvolutionEvaluationPlan(
            evaluation_id=f"{run.run_id}:candidate",
            role="candidate",
            label=candidate_label,
            target_ids=candidate_ids,
            task_ids=task_ids,
            status=EVOLUTION_EVALUATION_STATUS_PLANNED,
            metrics=EvolutionPlannedMetrics(),
            notes="planned candidate evaluation over the selected dataset",
        ),
        notes="harness plan prepared for isolated baseline and candidate execution over the same dataset",
    )


def execute_evolution_harness(
    plan: EvolutionHarnessPlan,
    dataset: EvolutionDataset,
    *,
    executor: EvolutionEvaluationExecutor | None = None,
) -> EvolutionHarnessPlan:
    _validate_harness_dataset_pair(plan, dataset)
    evaluation_executor = executor or summarize_dataset_evaluation
    baseline = _execute_evaluation(plan.baseline, dataset, executor=evaluation_executor)
    candidate = _execute_evaluation(plan.candidate, dataset, executor=evaluation_executor)
    failed = sum(
        1
        for evaluation in (baseline, candidate)
        if evaluation.status == EVOLUTION_EVALUATION_STATUS_FAILED
    )
    completed = sum(
        1
        for evaluation in (baseline, candidate)
        if evaluation.status == EVOLUTION_EVALUATION_STATUS_COMPLETED
    )
    if failed:
        notes = (
            f"harness executed over {len(plan.dataset_task_ids)} tasks; "
            f"{completed} evaluation(s) completed and {failed} failed"
        )
    else:
        notes = (
            f"harness executed baseline and candidate over {len(plan.dataset_task_ids)} tasks "
            "with isolated result capture"
        )
    return replace(plan, baseline=baseline, candidate=candidate, notes=notes)


def summarize_dataset_evaluation(
    evaluation: EvolutionEvaluationPlan,
    dataset: EvolutionDataset,
) -> EvolutionPlannedMetrics:
    trace_by_id = {trace.task_id: trace for trace in dataset.task_traces}
    traces = [trace_by_id[task_id] for task_id in evaluation.task_ids if task_id in trace_by_id]
    if not traces:
        raise ValueError("evaluation requires at least one matching task trace from the selected dataset")

    total = len(traces)
    passed_verify = sum(1 for trace in traces if trace.verify_status == "passed")
    verify_pass_rate = passed_verify / total if total else None
    conformance_status = _aggregate_conformance_status(trace.conformance_status for trace in traces)
    drift_count = sum(max(int(trace.drift_count), 0) for trace in traces)
    unresolved_warning_count = sum(max(int(trace.unresolved_warning_count), 0) for trace in traces)

    return EvolutionPlannedMetrics(
        verify_pass_rate=verify_pass_rate,
        conformance_status=conformance_status,
        drift_count=drift_count,
        unresolved_warning_count=unresolved_warning_count,
        runtime_ms=None,
        token_estimate=None,
        operator_reviewability=_derive_reviewability(
            verify_pass_rate=verify_pass_rate,
            conformance_status=conformance_status,
            unresolved_warning_count=unresolved_warning_count,
        ),
    )


def build_sisyphus_evaluation_request(
    evaluation: EvolutionEvaluationPlan,
    dataset: EvolutionDataset,
    *,
    title: str | None = None,
    message: str | None = None,
    instruction: str | None = None,
    task_type: str = "feature",
    slug: str | None = None,
    agent_id: str = "evolution-evaluation",
    role: str = "worker",
    provider: str = "codex",
    owned_paths: Sequence[str] | None = None,
    provider_args: Sequence[str] | None = None,
    source_context: dict[str, object] | None = None,
    auto_execute: bool = False,
    plan_reviewer: str = "evolution-harness",
    plan_review_notes: str | None = None,
    spec_reviewer: str = "evolution-harness",
    spec_review_notes: str | None = None,
) -> EvolutionSisyphusEvaluationRequest:
    merged_source_context = {
        "evolution_evaluation": True,
        "evolution_evaluation_id": evaluation.evaluation_id,
        "evolution_evaluation_role": evaluation.role,
        "evolution_target_ids": list(evaluation.target_ids),
        "evolution_task_ids": list(evaluation.task_ids),
        "evolution_dataset_generated_at": dataset.generated_at,
    }
    if source_context:
        merged_source_context.update(source_context)

    slug_suffix = evaluation.evaluation_id.lower().replace(":", "-")
    effective_owned_paths = _merge_owned_paths(
        ordered_target_source_paths(evaluation.target_ids),
        tuple(str(path) for path in owned_paths or ()),
    )
    return EvolutionSisyphusEvaluationRequest(
        title=title or f"Run {evaluation.role} evolution evaluation {evaluation.evaluation_id}",
        message=message or _default_sisyphus_evaluation_message(evaluation, dataset),
        instruction=instruction or _default_sisyphus_evaluation_instruction(evaluation),
        task_type=task_type,
        slug=slug or f"evolution-evaluation-{slug_suffix}",
        agent_id=agent_id,
        role=role,
        provider=provider,
        owned_paths=effective_owned_paths,
        provider_args=tuple(str(arg) for arg in provider_args or ()),
        source_context=merged_source_context,
        auto_execute=auto_execute,
        plan_reviewer=plan_reviewer,
        plan_review_notes=plan_review_notes,
        spec_reviewer=spec_reviewer,
        spec_review_notes=spec_review_notes,
    )


def execute_sisyphus_evaluation(
    evaluation: EvolutionEvaluationPlan,
    dataset: EvolutionDataset,
    *,
    request: EvolutionSisyphusEvaluationRequest | None = None,
) -> EvolutionEvaluationOutcome:
    from ..api import request_task
    from ..config import load_config
    from ..planning import approve_task_plan, freeze_task_spec
    from ..provider_wrapper import run_provider_wrapper
    from ..state import load_task_record

    metrics = summarize_dataset_evaluation(evaluation, dataset)
    sisyphus_request = request or build_sisyphus_evaluation_request(evaluation, dataset)
    repo_root = Path(dataset.repo_root)
    config = load_config(repo_root)

    request_outcome = request_task(
        repo_root=repo_root,
        config=config,
        message=sisyphus_request.message,
        title=sisyphus_request.title,
        task_type=sisyphus_request.task_type,
        slug=sisyphus_request.slug,
        instruction=sisyphus_request.instruction,
        agent_id=sisyphus_request.agent_id,
        role=sisyphus_request.role,
        provider=sisyphus_request.provider,
        owned_paths=list(sisyphus_request.owned_paths),
        provider_args=list(sisyphus_request.provider_args),
        source_context=sisyphus_request.source_context,
        auto_run=False,
    )
    if not request_outcome.ok or not request_outcome.task_id or request_outcome.task is None:
        detail = request_outcome.error or "failed to create Sisyphus evaluation task"
        raise EvolutionEvaluationExecutionError(
            detail,
            metrics=metrics,
            evidence=EvolutionEvaluationEvidence(
                mode=EVOLUTION_EVALUATION_EXECUTION_MODE_SISYPHUS_TASK,
                detail=detail,
                provider=sisyphus_request.provider,
                agent_id=sisyphus_request.agent_id,
            ),
        )

    task_id = str(request_outcome.task_id)
    task_snapshot = request_outcome.task

    plan_outcome = approve_task_plan(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        reviewer=sisyphus_request.plan_reviewer,
        notes=sisyphus_request.plan_review_notes or _default_plan_review_notes(evaluation),
    )
    if plan_outcome.plan_status != "approved":
        detail = f"Sisyphus evaluation task {task_id} plan approval failed: {plan_outcome.plan_status}"
        raise EvolutionEvaluationExecutionError(
            detail,
            metrics=metrics,
            evidence=_evaluation_evidence_from_task(
                task_snapshot,
                sisyphus_request,
                detail=detail,
                plan_status=plan_outcome.plan_status,
            ),
        )

    spec_outcome = freeze_task_spec(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        reviewer=sisyphus_request.spec_reviewer,
        notes=sisyphus_request.spec_review_notes or _default_spec_review_notes(evaluation),
    )
    if spec_outcome.spec_status != "frozen":
        detail = f"Sisyphus evaluation task {task_id} spec freeze failed: {spec_outcome.spec_status}"
        raise EvolutionEvaluationExecutionError(
            detail,
            metrics=metrics,
            evidence=_evaluation_evidence_from_task(
                task_snapshot,
                sisyphus_request,
                detail=detail,
                plan_status=plan_outcome.plan_status,
                spec_status=spec_outcome.spec_status,
                workflow_phase=spec_outcome.workflow_phase,
            ),
        )

    latest_task, _ = load_task_record(
        repo_root=repo_root,
        task_dir_name=config.task_dir,
        task_id=task_id,
    )
    try:
        materialization = materialize_evolution_evaluation(evaluation, task=latest_task)
    except EvolutionMaterializationError as exc:
        detail = f"Sisyphus evaluation task {task_id} materialization failed: {exc}"
        raise EvolutionEvaluationExecutionError(
            detail,
            metrics=metrics,
            evidence=_evaluation_evidence_from_task(
                latest_task,
                sisyphus_request,
                detail=detail,
                plan_status=plan_outcome.plan_status,
                spec_status=spec_outcome.spec_status,
                workflow_phase=spec_outcome.workflow_phase,
                materialization_status=EVOLUTION_MATERIALIZATION_STATUS_FAILED,
            ),
        )

    effective_owned_paths = _merge_owned_paths(
        sisyphus_request.owned_paths,
        materialization.file_paths,
        (materialization.manifest_path,),
    )

    exit_code = None
    if sisyphus_request.auto_execute:
        wrapper_args = ["task", task_id, sisyphus_request.agent_id, "--role", sisyphus_request.role]
        if sisyphus_request.instruction:
            wrapper_args.extend(["--instruction", sisyphus_request.instruction])
        for path in effective_owned_paths:
            wrapper_args.extend(["--owned-path", path])
        for arg in sisyphus_request.provider_args:
            wrapper_args.extend(["--provider-arg", arg])
        exit_code = run_provider_wrapper(
            sisyphus_request.provider,
            wrapper_args,
            repo_root=repo_root,
        )
        if exit_code != 0:
            latest_task, _ = load_task_record(
                repo_root=repo_root,
                task_dir_name=config.task_dir,
                task_id=task_id,
            )
            detail = f"Sisyphus evaluation task {task_id} exited with code {exit_code}"
            raise EvolutionEvaluationExecutionError(
                detail,
                metrics=metrics,
                evidence=_evaluation_evidence_from_task(
                    latest_task,
                    sisyphus_request,
                    detail=detail,
                    exit_code=exit_code,
                    materialization=materialization,
                ),
            )

    latest_task, _ = load_task_record(
        repo_root=repo_root,
        task_dir_name=config.task_dir,
        task_id=task_id,
    )
    detail = (
        f"created and executed isolated Sisyphus evaluation task {task_id} with {materialization.status}"
        if sisyphus_request.auto_execute
        else f"created isolated Sisyphus evaluation task {task_id} with {materialization.status}"
    )
    return EvolutionEvaluationOutcome(
        metrics=metrics,
        evidence=_evaluation_evidence_from_task(
            latest_task,
            sisyphus_request,
            detail=detail,
            exit_code=exit_code,
            materialization=materialization,
        ),
    )


def execute_worktree_backed_evaluation(
    evaluation: EvolutionEvaluationPlan,
    dataset: EvolutionDataset,
    *,
    request: EvolutionSisyphusEvaluationRequest | None = None,
) -> EvolutionEvaluationOutcome:
    context = _prepare_worktree_evaluation_context(
        evaluation=evaluation,
        dataset=dataset,
        request=request,
    )
    commands = build_worktree_evaluation_command_plan(evaluation, dataset)
    receipt_path, command_results = _run_worktree_evaluation_commands(
        commands=commands,
        worktree_root=Path(context.task["worktree_path"]),
        artifact_root=_artifact_root_from_materialization(
            worktree_root=Path(context.task["worktree_path"]),
            materialization=context.materialization,
        ),
    )
    metrics = _metrics_from_command_results(
        base_metrics=context.metrics,
        command_results=command_results,
    )
    passed_command_count = sum(1 for result in command_results if result.status == "passed")
    evidence = _evaluation_evidence_from_task(
        context.task,
        context.request,
        detail=(
            f"executed {len(command_results)} worktree-backed harness command(s) for "
            f"{context.task_id} with receipt {receipt_path}"
        ),
        plan_status=context.plan_status,
        spec_status=context.spec_status,
        workflow_phase=context.workflow_phase,
        materialization=context.materialization,
        mode=EVOLUTION_EVALUATION_EXECUTION_MODE_WORKTREE_HARNESS,
        execution_receipt_path=receipt_path,
        command_count=len(command_results),
        passed_command_count=passed_command_count,
    )
    if any(result.status == "failed" for result in command_results):
        raise EvolutionEvaluationExecutionError(
            f"worktree-backed evaluation command failed for {context.task_id}",
            metrics=metrics,
            evidence=evidence,
        )
    return EvolutionEvaluationOutcome(metrics=metrics, evidence=evidence)


def _validate_run_dataset_pair(run: EvolutionRun, dataset: EvolutionDataset) -> None:
    if run.repo_root != dataset.repo_root:
        raise ValueError(
            "run and dataset must target the same repository root: "
            f"{run.repo_root} != {dataset.repo_root}"
        )
    if not dataset.selected_task_ids:
        raise ValueError("harness planning requires a dataset with at least one selected task")


def _validate_harness_dataset_pair(plan: EvolutionHarnessPlan, dataset: EvolutionDataset) -> None:
    if plan.repo_root != dataset.repo_root:
        raise ValueError(
            "harness plan and dataset must target the same repository root: "
            f"{plan.repo_root} != {dataset.repo_root}"
        )
    if dataset.selected_task_ids != plan.dataset_task_ids:
        raise ValueError("harness plan and dataset must use the same selected task ids")


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


def _execute_evaluation(
    evaluation: EvolutionEvaluationPlan,
    dataset: EvolutionDataset,
    *,
    executor: EvolutionEvaluationExecutor,
) -> EvolutionEvaluationPlan:
    started = perf_counter()
    try:
        outcome = _coerce_evaluation_outcome(executor(evaluation, dataset))
        metrics = outcome.metrics
        runtime_ms = _elapsed_ms(started)
        if metrics.runtime_ms is None:
            metrics = replace(metrics, runtime_ms=runtime_ms)
        notes = (
            f"executed {evaluation.role} evaluation over {len(evaluation.task_ids)} tasks "
            f"and {len(evaluation.target_ids)} targets"
        )
        if outcome.evidence and outcome.evidence.task_id:
            notes = f"{notes} via {outcome.evidence.mode} {outcome.evidence.task_id}"
        return replace(
            evaluation,
            status=EVOLUTION_EVALUATION_STATUS_COMPLETED,
            metrics=metrics,
            notes=notes,
            evidence=outcome.evidence,
        )
    except EvolutionEvaluationExecutionError as exc:
        metrics = exc.metrics or EvolutionPlannedMetrics(
            operator_reviewability=EVOLUTION_OPERATOR_REVIEWABILITY_BLOCKED,
        )
        if metrics.runtime_ms is None:
            metrics = replace(metrics, runtime_ms=_elapsed_ms(started))
        return replace(
            evaluation,
            status=EVOLUTION_EVALUATION_STATUS_FAILED,
            metrics=metrics,
            notes=f"{evaluation.role} evaluation failed: {exc}",
            evidence=exc.evidence,
        )
    except Exception as exc:
        return replace(
            evaluation,
            status=EVOLUTION_EVALUATION_STATUS_FAILED,
            metrics=EvolutionPlannedMetrics(
                runtime_ms=_elapsed_ms(started),
                operator_reviewability=EVOLUTION_OPERATOR_REVIEWABILITY_BLOCKED,
            ),
            notes=f"{evaluation.role} evaluation failed: {exc}",
        )


def _coerce_evaluation_outcome(
    result: EvolutionEvaluationOutcome | EvolutionPlannedMetrics,
) -> EvolutionEvaluationOutcome:
    if isinstance(result, EvolutionEvaluationOutcome):
        return result
    if isinstance(result, EvolutionPlannedMetrics):
        return EvolutionEvaluationOutcome(metrics=result)
    raise TypeError(
        "evolution evaluation executor must return EvolutionEvaluationOutcome or EvolutionPlannedMetrics"
    )


def _elapsed_ms(started: float) -> int:
    return max(1, int((perf_counter() - started) * 1000))


def _aggregate_conformance_status(statuses: Iterable[str]) -> str:
    normalized = {normalize_conformance_status(status) for status in statuses if status}
    if CONFORMANCE_RED in normalized:
        return CONFORMANCE_RED
    if CONFORMANCE_YELLOW in normalized:
        return CONFORMANCE_YELLOW
    return CONFORMANCE_GREEN


def _derive_reviewability(
    *,
    verify_pass_rate: float | None,
    conformance_status: str | None,
    unresolved_warning_count: int,
) -> str:
    status = normalize_conformance_status(conformance_status)
    if status == CONFORMANCE_RED:
        return EVOLUTION_OPERATOR_REVIEWABILITY_BLOCKED
    if verify_pass_rate is None:
        return EVOLUTION_OPERATOR_REVIEWABILITY_LOW
    if verify_pass_rate >= 1.0 and unresolved_warning_count == 0 and status == CONFORMANCE_GREEN:
        return EVOLUTION_OPERATOR_REVIEWABILITY_HIGH
    if verify_pass_rate >= 0.75 and status != CONFORMANCE_RED:
        return EVOLUTION_OPERATOR_REVIEWABILITY_MEDIUM
    return EVOLUTION_OPERATOR_REVIEWABILITY_LOW


def _default_sisyphus_evaluation_message(
    evaluation: EvolutionEvaluationPlan,
    dataset: EvolutionDataset,
) -> str:
    target_ids = ", ".join(evaluation.target_ids) or "none"
    task_ids = ", ".join(evaluation.task_ids) or "none"
    return (
        f"Run the {evaluation.role} evolution evaluation in an isolated Sisyphus task/worktree.\n\n"
        f"Evaluation id: {evaluation.evaluation_id}\n"
        f"Targets: {target_ids}\n"
        f"Selected tasks: {task_ids}\n"
        f"Dataset generated at: {dataset.generated_at}"
    )


def _default_sisyphus_evaluation_instruction(evaluation: EvolutionEvaluationPlan) -> str:
    return (
        f"Prepare isolated execution evidence for `{evaluation.evaluation_id}`. "
        "Work only inside this dedicated Sisyphus task worktree. "
        "Do not mutate live task state outside the isolated evaluation task."
    )


def _default_plan_review_notes(evaluation: EvolutionEvaluationPlan) -> str:
    return f"Automatic plan approval for isolated evolution evaluation {evaluation.evaluation_id}."


def _default_spec_review_notes(evaluation: EvolutionEvaluationPlan) -> str:
    return f"Automatic spec freeze for isolated evolution evaluation {evaluation.evaluation_id}."


def _evaluation_evidence_from_task(
    task: dict,
    request: EvolutionSisyphusEvaluationRequest,
    *,
    detail: str,
    exit_code: int | None = None,
    plan_status: str | None = None,
    spec_status: str | None = None,
    workflow_phase: str | None = None,
    materialization: EvolutionMaterialization | None = None,
    materialization_status: str | None = None,
    mode: str = EVOLUTION_EVALUATION_EXECUTION_MODE_SISYPHUS_TASK,
    execution_receipt_path: str | None = None,
    command_count: int = 0,
    passed_command_count: int = 0,
) -> EvolutionEvaluationEvidence:
    return EvolutionEvaluationEvidence(
        mode=mode,
        detail=detail,
        task_id=optional_str(task.get("id")),
        branch=optional_str(task.get("branch")),
        worktree_path=optional_str(task.get("worktree_path")),
        provider=request.provider,
        agent_id=request.agent_id,
        task_status=optional_str(task.get("status")),
        plan_status=plan_status or optional_str(task.get("plan_status")),
        spec_status=spec_status or optional_str(task.get("spec_status")),
        workflow_phase=workflow_phase or optional_str(task.get("workflow_phase")),
        exit_code=exit_code,
        materialization_status=materialization_status or (materialization.status if materialization else None),
        materialization_manifest_path=materialization.manifest_path if materialization else None,
        materialization_snapshot_root=materialization.snapshot_root if materialization else None,
        materialized_target_ids=materialization.target_ids if materialization else (),
        materialized_file_paths=materialization.file_paths if materialization else (),
        execution_receipt_path=execution_receipt_path,
        command_count=command_count,
        passed_command_count=passed_command_count,
    )


def _merge_owned_paths(*groups: Sequence[str]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for path in group:
            normalized = str(path).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
    return tuple(merged)


@dataclass(frozen=True, slots=True)
class _PreparedWorktreeEvaluationContext:
    request: EvolutionSisyphusEvaluationRequest
    task_id: str
    task: dict
    metrics: EvolutionPlannedMetrics
    plan_status: str
    spec_status: str
    workflow_phase: str | None
    materialization: EvolutionMaterialization


def _prepare_worktree_evaluation_context(
    *,
    evaluation: EvolutionEvaluationPlan,
    dataset: EvolutionDataset,
    request: EvolutionSisyphusEvaluationRequest | None,
) -> _PreparedWorktreeEvaluationContext:
    from ..api import request_task
    from ..config import load_config
    from ..planning import approve_task_plan, freeze_task_spec
    from ..state import load_task_record

    metrics = summarize_dataset_evaluation(evaluation, dataset)
    sisyphus_request = request or build_sisyphus_evaluation_request(evaluation, dataset)
    repo_root = Path(dataset.repo_root)
    config = load_config(repo_root)

    request_outcome = request_task(
        repo_root=repo_root,
        config=config,
        message=sisyphus_request.message,
        title=sisyphus_request.title,
        task_type=sisyphus_request.task_type,
        slug=sisyphus_request.slug,
        instruction=sisyphus_request.instruction,
        agent_id=sisyphus_request.agent_id,
        role=sisyphus_request.role,
        provider=sisyphus_request.provider,
        owned_paths=list(sisyphus_request.owned_paths),
        provider_args=list(sisyphus_request.provider_args),
        source_context=sisyphus_request.source_context,
        auto_run=False,
    )
    if not request_outcome.ok or not request_outcome.task_id or request_outcome.task is None:
        detail = request_outcome.error or "failed to create Sisyphus evaluation task"
        raise EvolutionEvaluationExecutionError(
            detail,
            metrics=metrics,
            evidence=EvolutionEvaluationEvidence(
                mode=EVOLUTION_EVALUATION_EXECUTION_MODE_WORKTREE_HARNESS,
                detail=detail,
                provider=sisyphus_request.provider,
                agent_id=sisyphus_request.agent_id,
            ),
        )

    task_id = str(request_outcome.task_id)
    task_snapshot = request_outcome.task
    plan_outcome = approve_task_plan(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        reviewer=sisyphus_request.plan_reviewer,
        notes=sisyphus_request.plan_review_notes or _default_plan_review_notes(evaluation),
    )
    if plan_outcome.plan_status != "approved":
        detail = f"Sisyphus evaluation task {task_id} plan approval failed: {plan_outcome.plan_status}"
        raise EvolutionEvaluationExecutionError(
            detail,
            metrics=metrics,
            evidence=_evaluation_evidence_from_task(
                task_snapshot,
                sisyphus_request,
                detail=detail,
                plan_status=plan_outcome.plan_status,
                mode=EVOLUTION_EVALUATION_EXECUTION_MODE_WORKTREE_HARNESS,
            ),
        )

    spec_outcome = freeze_task_spec(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        reviewer=sisyphus_request.spec_reviewer,
        notes=sisyphus_request.spec_review_notes or _default_spec_review_notes(evaluation),
    )
    if spec_outcome.spec_status != "frozen":
        detail = f"Sisyphus evaluation task {task_id} spec freeze failed: {spec_outcome.spec_status}"
        raise EvolutionEvaluationExecutionError(
            detail,
            metrics=metrics,
            evidence=_evaluation_evidence_from_task(
                task_snapshot,
                sisyphus_request,
                detail=detail,
                plan_status=plan_outcome.plan_status,
                spec_status=spec_outcome.spec_status,
                workflow_phase=spec_outcome.workflow_phase,
                mode=EVOLUTION_EVALUATION_EXECUTION_MODE_WORKTREE_HARNESS,
            ),
        )

    latest_task, _ = load_task_record(
        repo_root=repo_root,
        task_dir_name=config.task_dir,
        task_id=task_id,
    )
    try:
        materialization = materialize_evolution_evaluation(evaluation, task=latest_task)
    except EvolutionMaterializationError as exc:
        detail = f"Sisyphus evaluation task {task_id} materialization failed: {exc}"
        raise EvolutionEvaluationExecutionError(
            detail,
            metrics=metrics,
            evidence=_evaluation_evidence_from_task(
                latest_task,
                sisyphus_request,
                detail=detail,
                plan_status=plan_outcome.plan_status,
                spec_status=spec_outcome.spec_status,
                workflow_phase=spec_outcome.workflow_phase,
                materialization_status=EVOLUTION_MATERIALIZATION_STATUS_FAILED,
                mode=EVOLUTION_EVALUATION_EXECUTION_MODE_WORKTREE_HARNESS,
            ),
        )
    return _PreparedWorktreeEvaluationContext(
        request=sisyphus_request,
        task_id=task_id,
        task=latest_task,
        metrics=metrics,
        plan_status=plan_outcome.plan_status,
        spec_status=spec_outcome.spec_status,
        workflow_phase=spec_outcome.workflow_phase,
        materialization=materialization,
    )


def build_worktree_evaluation_command_plan(
    evaluation: EvolutionEvaluationPlan,
    dataset: EvolutionDataset,
) -> tuple[EvolutionWorktreeCommand, ...]:
    trace_by_id = {trace.task_id: trace for trace in dataset.task_traces}
    commands: list[EvolutionWorktreeCommand] = []
    seen: set[str] = set()
    for task_id in evaluation.task_ids:
        trace = trace_by_id.get(task_id)
        if trace is None:
            continue
        command_inputs = [
            ("verify_result", result.command)
            for result in trace.verify_results
            if result.command.strip()
        ]
        if not command_inputs:
            command_inputs = [
                ("verify_command", command)
                for command in trace.verify_commands
                if command.strip()
            ]
        for source, original_command in command_inputs:
            normalized_command = _normalize_worktree_command(original_command)
            if not normalized_command or normalized_command in seen:
                continue
            seen.add(normalized_command)
            commands.append(
                EvolutionWorktreeCommand(
                    source_task_id=task_id,
                    source=source,
                    original_command=original_command,
                    normalized_command=normalized_command,
                )
            )
    if commands:
        return tuple(commands)
    raise EvolutionEvaluationExecutionError(
        f"no executable verify/test commands are available for evaluation {evaluation.evaluation_id}",
        metrics=EvolutionPlannedMetrics(operator_reviewability=EVOLUTION_OPERATOR_REVIEWABILITY_BLOCKED),
    )


def _normalize_worktree_command(command: str) -> str:
    normalized = str(command).strip()
    if not normalized:
        return ""
    if normalized.startswith("cd ") and "&&" in normalized:
        prefix, remainder = normalized.split("&&", 1)
        if prefix.strip().startswith("cd "):
            normalized = remainder.strip()
    return normalized


def _run_worktree_evaluation_commands(
    *,
    commands: Sequence[EvolutionWorktreeCommand],
    worktree_root: Path,
    artifact_root: Path,
) -> tuple[str, tuple[EvolutionWorktreeCommandResult, ...]]:
    execution_root = artifact_root / "execution"
    execution_root.mkdir(parents=True, exist_ok=True)
    results: list[EvolutionWorktreeCommandResult] = []
    for index, command in enumerate(commands, start=1):
        started = perf_counter()
        completed = subprocess.run(
            command.normalized_command,
            cwd=worktree_root,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        runtime_ms = _elapsed_ms(started)
        stdout_path = execution_root / f"command-{index:03d}.stdout.txt"
        stderr_path = execution_root / f"command-{index:03d}.stderr.txt"
        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")
        output_excerpt = (completed.stdout or completed.stderr or "").strip().splitlines()
        results.append(
            EvolutionWorktreeCommandResult(
                source_task_id=command.source_task_id,
                source=command.source,
                original_command=command.original_command,
                normalized_command=command.normalized_command,
                status="passed" if completed.returncode == 0 else "failed",
                exit_code=completed.returncode,
                runtime_ms=runtime_ms,
                stdout_path=stdout_path.relative_to(worktree_root).as_posix(),
                stderr_path=stderr_path.relative_to(worktree_root).as_posix(),
                output_excerpt=output_excerpt[-1][:200] if output_excerpt else None,
            )
        )
    receipt_path = execution_root / "execution_receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "command_count": len(results),
                "passed_command_count": sum(1 for result in results if result.status == "passed"),
                "results": [
                    {
                        "source_task_id": result.source_task_id,
                        "source": result.source,
                        "original_command": result.original_command,
                        "normalized_command": result.normalized_command,
                        "status": result.status,
                        "exit_code": result.exit_code,
                        "runtime_ms": result.runtime_ms,
                        "stdout_path": result.stdout_path,
                        "stderr_path": result.stderr_path,
                        "output_excerpt": result.output_excerpt,
                    }
                    for result in results
                ],
                "recorded_at": utc_now(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return receipt_path.relative_to(worktree_root).as_posix(), tuple(results)


def _metrics_from_command_results(
    *,
    base_metrics: EvolutionPlannedMetrics,
    command_results: Sequence[EvolutionWorktreeCommandResult],
) -> EvolutionPlannedMetrics:
    command_count = len(command_results)
    passed_command_count = sum(1 for result in command_results if result.status == "passed")
    verify_pass_rate = passed_command_count / command_count if command_count else None
    return replace(
        base_metrics,
        verify_pass_rate=verify_pass_rate,
        runtime_ms=sum(result.runtime_ms for result in command_results),
        operator_reviewability=_derive_reviewability(
            verify_pass_rate=verify_pass_rate,
            conformance_status=base_metrics.conformance_status,
            unresolved_warning_count=base_metrics.unresolved_warning_count or 0,
        ),
    )


def _artifact_root_from_materialization(
    *,
    worktree_root: Path,
    materialization: EvolutionMaterialization,
) -> Path:
    return worktree_root / Path(materialization.manifest_path).parent
