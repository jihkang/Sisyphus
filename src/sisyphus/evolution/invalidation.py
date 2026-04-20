from __future__ import annotations

from dataclasses import dataclass

from ..utils import required_str
from .artifacts import (
    EvolutionArtifactRef,
    EvolutionFollowupRequestArtifact,
    dedupe_artifact_refs,
)


EVOLUTION_INVALIDATION_CHANGE_FOLLOWUP_REQUEST = "followup_request_changed"
EVOLUTION_INVALIDATION_CHANGE_EXECUTION_RECEIPT = "execution_receipt_changed"
EVOLUTION_INVALIDATION_CHANGE_VERIFICATION = "verification_changed"
EVOLUTION_INVALIDATION_CHANGE_REVIEW_GATES = "review_gates_changed"
EVOLUTION_INVALIDATION_CHANGE_ENVELOPE = "envelope_changed"

EVOLUTION_INVALIDATION_ACTION_RECREATE_FOLLOWUP_REQUEST = "recreate_followup_request"
EVOLUTION_INVALIDATION_ACTION_REPROJECT_RECEIPTS = "reproject_execution_receipts"
EVOLUTION_INVALIDATION_ACTION_REPROJECT_VERIFICATION = "reproject_verification_artifacts"
EVOLUTION_INVALIDATION_ACTION_RERUN_PROMOTION_GATE = "rerun_promotion_gate"
EVOLUTION_INVALIDATION_ACTION_RERECORD_ENVELOPE = "rerecord_decision_envelope"


@dataclass(frozen=True, slots=True)
class EvolutionInvalidationChange:
    change_kind: str
    detail: str
    stale_artifact_refs: tuple[EvolutionArtifactRef, ...] = ()


@dataclass(frozen=True, slots=True)
class EvolutionInvalidationOutcome:
    run_id: str
    candidate_id: str
    followup_task_id: str | None
    change_kinds: tuple[str, ...]
    change_details: tuple[str, ...]
    stale_artifact_refs: tuple[EvolutionArtifactRef, ...]
    remediation_actions: tuple[str, ...]
    notes: str


def evaluate_evolution_invalidation(
    followup_request: EvolutionFollowupRequestArtifact,
    *,
    changes: tuple[EvolutionInvalidationChange, ...],
) -> EvolutionInvalidationOutcome:
    run_id = required_str(followup_request.run_id, "followup_request.run_id")
    candidate_id = required_str(followup_request.candidate_id, "followup_request.candidate_id")
    if not changes:
        raise ValueError("evolution invalidation requires at least one change")

    change_kinds: list[str] = []
    change_details: list[str] = []
    stale_artifact_refs: list[EvolutionArtifactRef] = []
    remediation_actions: list[str] = []
    seen_change_kinds: set[str] = set()
    seen_actions: set[str] = set()

    for change in changes:
        change_kind = required_str(change.change_kind, "change.change_kind").strip()
        detail = required_str(change.detail, "change.detail").strip()
        if change_kind not in _CHANGE_ACTIONS:
            raise ValueError(f"unsupported evolution invalidation change kind: {change_kind}")

        if change_kind not in seen_change_kinds:
            seen_change_kinds.add(change_kind)
            change_kinds.append(change_kind)
        change_details.append(detail)

        stale_artifact_refs.extend(_stale_refs_for_change(followup_request, change_kind, change))
        for action in _CHANGE_ACTIONS[change_kind]:
            if action in seen_actions:
                continue
            seen_actions.add(action)
            remediation_actions.append(action)

    return EvolutionInvalidationOutcome(
        run_id=run_id,
        candidate_id=candidate_id,
        followup_task_id=followup_request.followup_task_id,
        change_kinds=tuple(change_kinds),
        change_details=tuple(change_details),
        stale_artifact_refs=dedupe_artifact_refs(stale_artifact_refs),
        remediation_actions=tuple(remediation_actions),
        notes=f"invalidation required for {', '.join(change_kinds)}",
    )


_CHANGE_ACTIONS: dict[str, tuple[str, ...]] = {
    EVOLUTION_INVALIDATION_CHANGE_FOLLOWUP_REQUEST: (
        EVOLUTION_INVALIDATION_ACTION_RECREATE_FOLLOWUP_REQUEST,
        EVOLUTION_INVALIDATION_ACTION_RERUN_PROMOTION_GATE,
        EVOLUTION_INVALIDATION_ACTION_RERECORD_ENVELOPE,
    ),
    EVOLUTION_INVALIDATION_CHANGE_EXECUTION_RECEIPT: (
        EVOLUTION_INVALIDATION_ACTION_REPROJECT_RECEIPTS,
        EVOLUTION_INVALIDATION_ACTION_REPROJECT_VERIFICATION,
        EVOLUTION_INVALIDATION_ACTION_RERUN_PROMOTION_GATE,
        EVOLUTION_INVALIDATION_ACTION_RERECORD_ENVELOPE,
    ),
    EVOLUTION_INVALIDATION_CHANGE_VERIFICATION: (
        EVOLUTION_INVALIDATION_ACTION_REPROJECT_VERIFICATION,
        EVOLUTION_INVALIDATION_ACTION_RERUN_PROMOTION_GATE,
        EVOLUTION_INVALIDATION_ACTION_RERECORD_ENVELOPE,
    ),
    EVOLUTION_INVALIDATION_CHANGE_REVIEW_GATES: (
        EVOLUTION_INVALIDATION_ACTION_RECREATE_FOLLOWUP_REQUEST,
        EVOLUTION_INVALIDATION_ACTION_RERUN_PROMOTION_GATE,
        EVOLUTION_INVALIDATION_ACTION_RERECORD_ENVELOPE,
    ),
    EVOLUTION_INVALIDATION_CHANGE_ENVELOPE: (
        EVOLUTION_INVALIDATION_ACTION_RERECORD_ENVELOPE,
    ),
}


def _stale_refs_for_change(
    followup_request: EvolutionFollowupRequestArtifact,
    change_kind: str,
    change: EvolutionInvalidationChange,
) -> tuple[EvolutionArtifactRef, ...]:
    if change_kind in {
        EVOLUTION_INVALIDATION_CHANGE_FOLLOWUP_REQUEST,
        EVOLUTION_INVALIDATION_CHANGE_REVIEW_GATES,
    }:
        return dedupe_artifact_refs(
            (
                followup_request.to_ref(notes=change_kind),
                *change.stale_artifact_refs,
            )
        )
    return dedupe_artifact_refs(change.stale_artifact_refs)
