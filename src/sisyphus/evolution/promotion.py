from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import SisyphusConfig
from .artifacts import (
    EvolutionArtifactRef,
    EvolutionFollowupRequestArtifact,
    PromotionDecisionArtifact,
    dedupe_artifact_refs,
)
from .constraints import EvolutionConstraintResult
from .event_bus import EVOLUTION_EVENT_DECISION_RECORDED, publish_evolution_event
from .fitness import EvolutionFitnessResult
from .receipts import EvolutionFollowupExecutionProjection
from .runner import EvolutionInvalidationRecord
from .verification import EvolutionFollowupVerificationProjection


EVOLUTION_PROMOTION_GATE_STATUS_BLOCKED = "blocked"
EVOLUTION_PROMOTION_GATE_STATUS_READY_FOR_REVIEW = "ready_for_review"
EVOLUTION_PROMOTION_GATE_STATUS_ELIGIBLE = "eligible_for_promotion"

EVOLUTION_PROMOTION_BLOCKER_SCOPE_HANDOFF = "handoff"
EVOLUTION_PROMOTION_BLOCKER_SCOPE_PROMOTION = "promotion"

EVOLUTION_ENVELOPE_STATUS_PROMOTION = "promotion"
EVOLUTION_ENVELOPE_STATUS_INVALIDATION = "invalidation"


@dataclass(frozen=True, slots=True)
class EvolutionPromotionBlocker:
    blocker_id: str
    scope: str
    detail: str
    artifact_refs: tuple[EvolutionArtifactRef, ...] = ()


@dataclass(frozen=True, slots=True)
class EvolutionPromotionGateResult:
    run_id: str
    candidate_id: str
    followup_task_id: str | None
    status: str
    reviewable_handoff_eligible: bool
    promotion_eligible: bool
    required_review_gates: tuple[str, ...]
    blocking_conditions: tuple[EvolutionPromotionBlocker, ...]
    evidence_refs: tuple[EvolutionArtifactRef, ...]
    notes: str


@dataclass(frozen=True, slots=True)
class EvolutionDecisionEnvelope:
    status: str
    promotion_decision: PromotionDecisionArtifact | None
    invalidation_record: EvolutionInvalidationRecord | None
    evidence_refs: tuple[EvolutionArtifactRef, ...]


def evaluate_evolution_promotion_gate(
    followup_request: EvolutionFollowupRequestArtifact,
    *,
    constraints: EvolutionConstraintResult | None,
    fitness: EvolutionFitnessResult | None,
    execution_projection: EvolutionFollowupExecutionProjection | None = None,
    verification_projection: EvolutionFollowupVerificationProjection | None = None,
) -> EvolutionPromotionGateResult:
    blockers: list[EvolutionPromotionBlocker] = []
    evidence_refs: list[EvolutionArtifactRef] = [
        followup_request.to_ref(notes="followup_request"),
    ]
    required_review_gates = tuple(str(gate) for gate in followup_request.required_review_gates if str(gate))

    if not required_review_gates:
        blockers.append(
            EvolutionPromotionBlocker(
                blocker_id="review_gates_missing",
                scope=EVOLUTION_PROMOTION_BLOCKER_SCOPE_HANDOFF,
                detail="follow-up request artifact does not record any review gates",
                artifact_refs=(followup_request.to_ref(notes="missing_review_gates"),),
            )
        )

    if constraints is None:
        blockers.append(
            EvolutionPromotionBlocker(
                blocker_id="constraints_missing",
                scope=EVOLUTION_PROMOTION_BLOCKER_SCOPE_HANDOFF,
                detail="promotion gate requires constraint evaluation before reviewable handoff",
            )
        )
    elif constraints.accepted is not True:
        blockers.append(
            EvolutionPromotionBlocker(
                blocker_id=f"constraints_{constraints.status}",
                scope=EVOLUTION_PROMOTION_BLOCKER_SCOPE_HANDOFF,
                detail=constraints.notes,
            )
        )

    if fitness is None:
        blockers.append(
            EvolutionPromotionBlocker(
                blocker_id="fitness_missing",
                scope=EVOLUTION_PROMOTION_BLOCKER_SCOPE_HANDOFF,
                detail="promotion gate requires fitness evaluation before reviewable handoff",
            )
        )
    elif fitness.eligible_for_promotion is not True:
        blockers.append(
            EvolutionPromotionBlocker(
                blocker_id=f"fitness_{fitness.status}",
                scope=EVOLUTION_PROMOTION_BLOCKER_SCOPE_HANDOFF,
                detail=fitness.notes,
            )
        )

    if execution_projection is None:
        blockers.append(
            EvolutionPromotionBlocker(
                blocker_id="execution_receipts_pending",
                scope=EVOLUTION_PROMOTION_BLOCKER_SCOPE_PROMOTION,
                detail="follow-up execution receipts are not projected yet",
                artifact_refs=(followup_request.to_ref(notes="followup_execution_pending"),),
            )
        )
    else:
        _validate_execution_projection(followup_request, execution_projection)
        execution_refs = tuple(
            receipt.to_ref(notes=receipt.receipt_kind)
            for receipt in execution_projection.execution_receipts
        )
        evidence_refs.extend(execution_refs)
        if any(task_run.status != "passed" for task_run in execution_projection.task_runs):
            blockers.append(
                EvolutionPromotionBlocker(
                    blocker_id="followup_execution_failed",
                    scope=EVOLUTION_PROMOTION_BLOCKER_SCOPE_PROMOTION,
                    detail="one or more follow-up task runs did not pass verification",
                    artifact_refs=execution_refs,
                )
            )

    if verification_projection is None:
        blockers.append(
            EvolutionPromotionBlocker(
                blocker_id="verification_artifacts_pending",
                scope=EVOLUTION_PROMOTION_BLOCKER_SCOPE_PROMOTION,
                detail="verification artifacts have not been projected from the follow-up task yet",
                artifact_refs=(followup_request.to_ref(notes="verification_pending"),),
            )
        )
    else:
        _validate_verification_projection(followup_request, verification_projection)
        verification_refs = tuple(
            artifact.to_ref(notes=artifact.result)
            for artifact in verification_projection.verification_artifacts
        )
        evidence_refs.extend(verification_refs)
        if any(artifact.result != "passed" for artifact in verification_projection.verification_artifacts):
            blockers.append(
                EvolutionPromotionBlocker(
                    blocker_id="verification_failed",
                    scope=EVOLUTION_PROMOTION_BLOCKER_SCOPE_PROMOTION,
                    detail="one or more verification artifacts are not passing",
                    artifact_refs=verification_refs,
                )
            )

    handoff_blockers = tuple(
        blocker for blocker in blockers if blocker.scope == EVOLUTION_PROMOTION_BLOCKER_SCOPE_HANDOFF
    )
    reviewable_handoff_eligible = not handoff_blockers
    promotion_eligible = reviewable_handoff_eligible and not blockers
    if promotion_eligible:
        status = EVOLUTION_PROMOTION_GATE_STATUS_ELIGIBLE
        notes = "candidate satisfied follow-up, execution, and verification obligations"
    elif reviewable_handoff_eligible:
        status = EVOLUTION_PROMOTION_GATE_STATUS_READY_FOR_REVIEW
        notes = "candidate is ready for reviewable handoff but promotion is still blocked on downstream obligations"
    else:
        status = EVOLUTION_PROMOTION_GATE_STATUS_BLOCKED
        notes = "candidate is blocked before reviewable handoff because required hard-state obligations are incomplete"

    return EvolutionPromotionGateResult(
        run_id=followup_request.run_id,
        candidate_id=followup_request.candidate_id,
        followup_task_id=followup_request.followup_task_id,
        status=status,
        reviewable_handoff_eligible=reviewable_handoff_eligible,
        promotion_eligible=promotion_eligible,
        required_review_gates=required_review_gates,
        blocking_conditions=tuple(blockers),
        evidence_refs=tuple(evidence_refs),
        notes=notes,
    )


def record_evolution_decision_envelope(
    gate_result: EvolutionPromotionGateResult,
    *,
    claim: str,
    repo_root: Path | None = None,
    config: SisyphusConfig | None = None,
) -> EvolutionDecisionEnvelope:
    run_id = str(gate_result.run_id).strip()
    candidate_id = str(gate_result.candidate_id).strip()
    if not run_id:
        raise ValueError("promotion gate result run_id is required")
    if not candidate_id:
        raise ValueError("promotion gate result candidate_id is required")

    evidence_refs = dedupe_artifact_refs(gate_result.evidence_refs)
    blocker_details = tuple(blocker.detail for blocker in gate_result.blocking_conditions)
    blocker_refs = dedupe_artifact_refs(
        tuple(
            artifact_ref
            for blocker in gate_result.blocking_conditions
            for artifact_ref in blocker.artifact_refs
        )
    )

    if gate_result.status in {
        EVOLUTION_PROMOTION_GATE_STATUS_READY_FOR_REVIEW,
        EVOLUTION_PROMOTION_GATE_STATUS_ELIGIBLE,
    }:
        decision = PromotionDecisionArtifact(
            artifact_id=_promotion_decision_artifact_id(
                run_id=run_id,
                candidate_id=candidate_id,
                status=gate_result.status,
            ),
            producing_stage=_promotion_stage_for_status(gate_result.status),
            status="recorded",
            run_id=run_id,
            candidate_id=candidate_id,
            decision=gate_result.status,
            claim=claim,
            followup_task_id=gate_result.followup_task_id,
            blocker_details=blocker_details,
            depends_on=evidence_refs or blocker_refs,
            evidence_refs=evidence_refs,
        )
        envelope = EvolutionDecisionEnvelope(
            status=EVOLUTION_ENVELOPE_STATUS_PROMOTION,
            promotion_decision=decision,
            invalidation_record=None,
            evidence_refs=evidence_refs,
        )
        _publish_decision_event(
            envelope,
            repo_root=repo_root,
            config=config,
            gate_result=gate_result,
        )
        return envelope

    if gate_result.status == EVOLUTION_PROMOTION_GATE_STATUS_BLOCKED:
        invalidation = EvolutionInvalidationRecord(
            record_id=_invalidation_record_id(run_id=run_id, candidate_id=candidate_id),
            run_id=run_id,
            candidate_id=candidate_id,
            reason=gate_result.notes,
            affected_artifacts=blocker_refs,
            evidence_refs=evidence_refs,
            blocker_details=blocker_details,
            followup_task_id=gate_result.followup_task_id,
            status=EVOLUTION_PROMOTION_GATE_STATUS_BLOCKED,
        )
        envelope = EvolutionDecisionEnvelope(
            status=EVOLUTION_ENVELOPE_STATUS_INVALIDATION,
            promotion_decision=None,
            invalidation_record=invalidation,
            evidence_refs=evidence_refs,
        )
        _publish_decision_event(
            envelope,
            repo_root=repo_root,
            config=config,
            gate_result=gate_result,
        )
        return envelope

    raise ValueError(f"unsupported promotion gate status: {gate_result.status}")


def _validate_execution_projection(
    followup_request: EvolutionFollowupRequestArtifact,
    execution_projection: EvolutionFollowupExecutionProjection,
) -> None:
    if execution_projection.source_run_id != followup_request.run_id:
        raise ValueError("execution projection run_id does not match follow-up request artifact")
    if execution_projection.candidate_id != followup_request.candidate_id:
        raise ValueError("execution projection candidate_id does not match follow-up request artifact")
    if (
        followup_request.followup_task_id is not None
        and execution_projection.followup_task_id != followup_request.followup_task_id
    ):
        raise ValueError("execution projection followup_task_id does not match follow-up request artifact")


def _validate_verification_projection(
    followup_request: EvolutionFollowupRequestArtifact,
    verification_projection: EvolutionFollowupVerificationProjection,
) -> None:
    if verification_projection.source_run_id != followup_request.run_id:
        raise ValueError("verification projection run_id does not match follow-up request artifact")
    if verification_projection.candidate_id != followup_request.candidate_id:
        raise ValueError("verification projection candidate_id does not match follow-up request artifact")
    if (
        followup_request.followup_task_id is not None
        and verification_projection.followup_task_id != followup_request.followup_task_id
    ):
        raise ValueError("verification projection followup_task_id does not match follow-up request artifact")


def _promotion_stage_for_status(status: str) -> str:
    if status == EVOLUTION_PROMOTION_GATE_STATUS_READY_FOR_REVIEW:
        return "ready_for_review"
    if status == EVOLUTION_PROMOTION_GATE_STATUS_ELIGIBLE:
        return "promoted"
    raise ValueError(f"unsupported promotion decision status: {status}")


def _promotion_decision_artifact_id(*, run_id: str, candidate_id: str, status: str) -> str:
    return f"artifact-{run_id}-{candidate_id}-promotion-decision-{status}"


def _invalidation_record_id(*, run_id: str, candidate_id: str) -> str:
    return f"record-{run_id}-{candidate_id}-invalidation"


def _publish_decision_event(
    envelope: EvolutionDecisionEnvelope,
    *,
    repo_root: Path | None,
    config: SisyphusConfig | None,
    gate_result: EvolutionPromotionGateResult,
) -> None:
    if repo_root is None:
        return

    promotion_decision_id = (
        envelope.promotion_decision.artifact_id
        if envelope.promotion_decision is not None
        else None
    )
    invalidation_record_id = (
        envelope.invalidation_record.record_id
        if envelope.invalidation_record is not None
        else None
    )
    publish_evolution_event(
        repo_root,
        config=config,
        event_type=EVOLUTION_EVENT_DECISION_RECORDED,
        source_module="evolution.promotion",
        data={
            "run_id": gate_result.run_id,
            "candidate_id": gate_result.candidate_id,
            "followup_task_id": gate_result.followup_task_id,
            "envelope_status": envelope.status,
            "gate_status": gate_result.status,
            "promotion_decision_id": promotion_decision_id,
            "invalidation_record_id": invalidation_record_id,
            "evidence_count": len(envelope.evidence_refs),
        },
    )
