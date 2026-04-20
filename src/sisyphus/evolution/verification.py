from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ..config import SisyphusConfig
from ..state import load_task_record
from ..utils import optional_str, required_str
from .artifacts import (
    EVOLUTION_ARTIFACT_STATUS_RECORDED,
    VerificationArtifact,
)
from .event_bus import EVOLUTION_EVENT_VERIFICATION_PROJECTED, publish_evolution_event
from .followup import extract_followup_source_context
from .receipts import EvolutionFollowupExecutionProjection, project_followup_execution_record


@dataclass(frozen=True, slots=True)
class EvolutionFollowupVerificationProjection:
    source_run_id: str
    candidate_id: str
    followup_task_id: str
    verification_artifacts: tuple[VerificationArtifact, ...]
    execution_projection: EvolutionFollowupExecutionProjection


def project_followup_verification(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
) -> EvolutionFollowupVerificationProjection:
    task, task_file = load_task_record(
        repo_root=repo_root,
        task_dir_name=config.task_dir,
        task_id=task_id,
    )
    projection = project_followup_verification_record(task=task, task_dir=task_file.parent)
    publish_evolution_event(
        repo_root,
        config=config,
        event_type=EVOLUTION_EVENT_VERIFICATION_PROJECTED,
        source_module="evolution.verification",
        data={
            "run_id": projection.source_run_id,
            "candidate_id": projection.candidate_id,
            "followup_task_id": projection.followup_task_id,
            "verification_count": len(projection.verification_artifacts),
            "verification_results": [
                artifact.result for artifact in projection.verification_artifacts
            ],
        },
    )
    return projection


def project_followup_verification_record(
    *,
    task: dict,
    task_dir: Path,
) -> EvolutionFollowupVerificationProjection:
    task_id = required_str(task.get("id"), "task.id")
    source_context = extract_followup_source_context(task, purpose="verification projection")
    source_run_id = required_str(source_context.get("source_run_id"), "source_context.source_run_id")
    candidate_id = required_str(source_context.get("candidate_id"), "source_context.candidate_id")
    obligations = _load_verification_obligations(
        source_context.get("expected_verification_obligations"),
        task_id=task_id,
    )
    execution_projection = project_followup_execution_record(task=task, task_dir=task_dir)
    receipt_refs = tuple(
        receipt.to_ref(notes=receipt.receipt_kind)
        for receipt in execution_projection.execution_receipts
    )
    verification_result = _derive_verification_result(
        verify_status=optional_str(task.get("verify_status")),
        execution_projection=execution_projection,
    )
    verification_artifacts = tuple(
        VerificationArtifact(
            artifact_id=_verification_artifact_id(task_id=task_id, index=index),
            producing_stage="followup_requested",
            status=EVOLUTION_ARTIFACT_STATUS_RECORDED,
            run_id=source_run_id,
            claim=claim,
            verification_method=method,
            verification_scope="followup_execution",
            result=verification_result,
            depends_on=receipt_refs,
            evidence_refs=receipt_refs,
        )
        for index, (claim, method) in enumerate(obligations, start=1)
    )
    return EvolutionFollowupVerificationProjection(
        source_run_id=source_run_id,
        candidate_id=candidate_id,
        followup_task_id=task_id,
        verification_artifacts=verification_artifacts,
        execution_projection=execution_projection,
    )


def _load_verification_obligations(
    raw_obligations: object,
    *,
    task_id: str,
) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw_obligations, Sequence) or isinstance(raw_obligations, (str, bytes)):
        raise ValueError(
            f"evolution follow-up task `{task_id}` has no verification obligations to project"
        )
    normalized: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw_obligation in enumerate(raw_obligations, start=1):
        if not isinstance(raw_obligation, Mapping):
            raise ValueError(
                f"evolution follow-up task `{task_id}` has invalid verification obligation at index {index}"
            )
        claim = str(required_str(raw_obligation.get("claim"), f"verification_obligation[{index}].claim")).strip()
        method = str(required_str(raw_obligation.get("method"), f"verification_obligation[{index}].method")).strip()
        normalized_pair = (claim, method)
        if normalized_pair in seen:
            continue
        seen.add(normalized_pair)
        normalized.append(normalized_pair)
    if not normalized:
        raise ValueError(
            f"evolution follow-up task `{task_id}` has no verification obligations to project"
        )
    return tuple(normalized)


def _derive_verification_result(
    *,
    verify_status: str | None,
    execution_projection: EvolutionFollowupExecutionProjection,
) -> str:
    task_run_statuses = {task_run.status for task_run in execution_projection.task_runs}
    if verify_status == "passed" and task_run_statuses == {"passed"}:
        return "passed"
    if verify_status in {"pending", "not_run"} or any(
        status not in {"passed", "failed"} for status in task_run_statuses
    ):
        return "pending"
    return "failed"


def _verification_artifact_id(*, task_id: str, index: int) -> str:
    return f"artifact-{task_id}-followup-verification-{index}"
