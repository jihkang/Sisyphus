from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ..evolution.dataset import EvolutionDataset
from ..evolution.harness import (
    EVOLUTION_EVALUATION_EXECUTION_MODE_SISYPHUS_TASK,
    EVOLUTION_EVALUATION_EXECUTION_MODE_WORKTREE_HARNESS,
    EvolutionEvaluationEvidence,
    EvolutionEvaluationExecutionError,
    EvolutionEvaluationOutcome,
    EvolutionEvaluationPlan,
    EvolutionPlannedMetrics,
    EvolutionSisyphusEvaluationRequest,
    EvolutionWorktreeCommand,
    EvolutionWorktreeCommandResult,
    build_sisyphus_evaluation_request,
    build_worktree_evaluation_command_plan,
    summarize_dataset_evaluation,
    utc_now,
)
from ..evolution.materialization import (
    EVOLUTION_MATERIALIZATION_STATUS_FAILED,
    EvolutionMaterialization,
    EvolutionMaterializationError,
)
from ..infra.evolution.materialization import RepositoryEvolutionMaterializer
from ..infra.evolution.evaluation import RepositoryEvolutionCommandRunner
from ..shared.coerce import optional_str


def materialize_evolution_evaluation(evaluation, *, task: dict) -> EvolutionMaterialization:
    return RepositoryEvolutionMaterializer().materialize(evaluation, task=task)


def execute_sisyphus_evaluation(
    evaluation: EvolutionEvaluationPlan,
    dataset: EvolutionDataset,
    *,
    request: EvolutionSisyphusEvaluationRequest | None = None,
) -> EvolutionEvaluationOutcome:
    # Resolve these compatibility surfaces at call time so supported patch points
    # continue to observe the same execution boundary.
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
    receipt_path, command_results = RepositoryEvolutionCommandRunner().run(
        commands=commands,
        worktree_root=Path(context.task["worktree_path"]),
        artifact_root=_artifact_root_from_materialization(
            worktree_root=Path(context.task["worktree_path"]),
            materialization=context.materialization,
        ),
        recorded_at=utc_now(),
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


class _PreparedWorktreeEvaluationContext:
    def __init__(
        self,
        *,
        request: EvolutionSisyphusEvaluationRequest,
        task_id: str,
        task: dict,
        metrics: EvolutionPlannedMetrics,
        plan_status: str,
        spec_status: str,
        workflow_phase: str | None,
        materialization: EvolutionMaterialization,
    ) -> None:
        self.request = request
        self.task_id = task_id
        self.task = task
        self.metrics = metrics
        self.plan_status = plan_status
        self.spec_status = spec_status
        self.workflow_phase = workflow_phase
        self.materialization = materialization


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


def _metrics_from_command_results(
    *,
    base_metrics: EvolutionPlannedMetrics,
    command_results: Sequence[EvolutionWorktreeCommandResult],
) -> EvolutionPlannedMetrics:
    from dataclasses import replace

    command_count = len(command_results)
    passed_command_count = sum(1 for result in command_results if result.status == "passed")
    verify_pass_rate = passed_command_count / command_count if command_count else None
    if base_metrics.conformance_status == "red":
        reviewability = "blocked"
    elif verify_pass_rate is None:
        reviewability = "low"
    elif (
        verify_pass_rate >= 1.0
        and (base_metrics.unresolved_warning_count or 0) == 0
        and base_metrics.conformance_status == "green"
    ):
        reviewability = "high"
    elif verify_pass_rate >= 0.75:
        reviewability = "medium"
    else:
        reviewability = "low"
    return replace(
        base_metrics,
        verify_pass_rate=verify_pass_rate,
        runtime_ms=sum(result.runtime_ms for result in command_results),
        operator_reviewability=reviewability,
    )


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


def _default_plan_review_notes(evaluation: EvolutionEvaluationPlan) -> str:
    return f"Automatic plan approval for isolated evolution evaluation {evaluation.evaluation_id}."


def _default_spec_review_notes(evaluation: EvolutionEvaluationPlan) -> str:
    return f"Automatic spec freeze for isolated evolution evaluation {evaluation.evaluation_id}."


def _artifact_root_from_materialization(
    *,
    worktree_root: Path,
    materialization: EvolutionMaterialization,
) -> Path:
    return worktree_root / Path(materialization.manifest_path).parent


__all__ = [
    "execute_sisyphus_evaluation",
    "execute_worktree_backed_evaluation",
    "materialize_evolution_evaluation",
]
