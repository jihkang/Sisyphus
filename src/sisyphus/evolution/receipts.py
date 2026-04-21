from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..artifacts import TaskRunRef
from ..config import SisyphusConfig
from ..promotion_state import (
    PROMOTION_STATUS_MERGED,
    PROMOTION_STATUS_RECORDED,
    promotion_summary,
)
from ..state import load_task_record
from ..utils import required_str
from .artifacts import (
    EVOLUTION_ARTIFACT_STATUS_RECORDED,
    ExecutionReceiptArtifact,
)
from .event_bus import EVOLUTION_EVENT_EXECUTION_PROJECTED, publish_evolution_event
from .followup import extract_followup_source_context, relative_task_locator


@dataclass(frozen=True, slots=True)
class EvolutionFollowupExecutionProjection:
    source_run_id: str
    candidate_id: str
    followup_task_id: str
    execution_receipts: tuple[ExecutionReceiptArtifact, ...]
    task_runs: tuple[TaskRunRef, ...]


def project_followup_execution(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
) -> EvolutionFollowupExecutionProjection:
    task, task_file = load_task_record(
        repo_root=repo_root,
        task_dir_name=config.task_dir,
        task_id=task_id,
    )
    projection = project_followup_execution_record(task=task, task_dir=task_file.parent)
    publish_evolution_event(
        repo_root,
        config=config,
        event_type=EVOLUTION_EVENT_EXECUTION_PROJECTED,
        source_module="evolution.receipts",
        data={
            "run_id": projection.source_run_id,
            "candidate_id": projection.candidate_id,
            "followup_task_id": projection.followup_task_id,
            "receipt_count": len(projection.execution_receipts),
            "task_run_count": len(projection.task_runs),
            "receipt_kinds": [receipt.receipt_kind for receipt in projection.execution_receipts],
        },
    )
    return projection


def project_followup_execution_record(
    *,
    task: dict,
    task_dir: Path,
) -> EvolutionFollowupExecutionProjection:
    task_id = required_str(task.get("id"), "task.id")
    source_context = extract_followup_source_context(task, purpose="receipt projection")
    source_run_id = required_str(source_context.get("source_run_id"), "source_context.source_run_id")
    candidate_id = required_str(source_context.get("candidate_id"), "source_context.candidate_id")

    verify_relative = required_str(task.get("docs", {}).get("verify"), "task.docs.verify")
    verify_path = task_dir / verify_relative
    if not verify_path.exists():
        raise FileNotFoundError(
            f"evolution follow-up task `{task_id}` is missing verify receipt document `{verify_relative}`"
        )

    verify_results = task.get("last_verify_results", [])
    if not isinstance(verify_results, list) or not verify_results:
        raise ValueError(
            f"evolution follow-up task `{task_id}` has no verify results to project"
        )

    verify_locator = relative_task_locator(task=task, relative_path=verify_relative)
    execution_receipts: list[ExecutionReceiptArtifact] = []
    task_runs: list[TaskRunRef] = []
    for index, result in enumerate(verify_results, start=1):
        status = required_str(result.get("status"), f"last_verify_results[{index}].status")
        receipt_artifact = ExecutionReceiptArtifact(
            artifact_id=_receipt_artifact_id(task_id=task_id, suffix=f"verify-{index}"),
            producing_stage="followup_requested",
            status=EVOLUTION_ARTIFACT_STATUS_RECORDED,
            run_id=source_run_id,
            task_id=task_id,
            receipt_kind=f"verify_command_{index}",
            receipt_locator=verify_locator,
        )
        execution_receipts.append(receipt_artifact)
        task_runs.append(
            TaskRunRef(
                task_id=task_id,
                run_id=f"{task_id}:verify:{index}",
                status=status,
                receipt_locator=receipt_artifact.artifact_id,
            )
        )

    promotion = promotion_summary(task)
    if promotion.get("status") in {PROMOTION_STATUS_MERGED, PROMOTION_STATUS_RECORDED} and promotion.get("receipt_path"):
        promotion_relative = required_str(
            promotion.get("receipt_path"),
            "task.promotion.receipt_path",
        )
        promotion_path = task_dir / promotion_relative
        if not promotion_path.exists():
            raise FileNotFoundError(
                f"evolution follow-up task `{task_id}` references missing promotion receipt `{promotion_relative}`"
            )
        execution_receipts.append(
            ExecutionReceiptArtifact(
                artifact_id=_receipt_artifact_id(task_id=task_id, suffix="promotion"),
                producing_stage="followup_requested",
                status=EVOLUTION_ARTIFACT_STATUS_RECORDED,
                run_id=source_run_id,
                task_id=task_id,
                receipt_kind="promotion_receipt",
                receipt_locator=relative_task_locator(task=task, relative_path=promotion_relative),
            )
        )

    return EvolutionFollowupExecutionProjection(
        source_run_id=source_run_id,
        candidate_id=candidate_id,
        followup_task_id=task_id,
        execution_receipts=tuple(execution_receipts),
        task_runs=tuple(task_runs),
    )
def _receipt_artifact_id(*, task_id: str, suffix: str) -> str:
    return f"artifact-{task_id}-followup-receipt-{suffix}"
