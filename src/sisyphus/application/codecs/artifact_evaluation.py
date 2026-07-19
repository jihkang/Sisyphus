from __future__ import annotations

from ...domain.artifact.evaluation import (
    ArtifactPromotionDecision,
    FeatureChangeEvaluation,
    InvalidationRecord,
)
from .artifact_dsl import encode_obligation_intent
from .artifacts import encode_artifact_ref


def encode_artifact_promotion_decision(
    value: ArtifactPromotionDecision,
) -> dict[str, object]:
    return {
        "artifact_id": value.artifact_id,
        "decision": value.decision,
        "missing_requirements": list(value.missing_requirements),
        "blocking_reasons": list(value.blocking_reasons),
        "required_actions": list(value.required_actions),
        "evidence_refs": [encode_artifact_ref(ref) for ref in value.evidence_refs],
    }


def encode_invalidation_record(value: InvalidationRecord) -> dict[str, object]:
    return {
        "artifact_id": value.artifact_id,
        "status": value.status,
        "stale_inputs": [encode_artifact_ref(ref) for ref in value.stale_inputs],
        "invalid_inputs": [encode_artifact_ref(ref) for ref in value.invalid_inputs],
        "reasons": list(value.reasons),
        "required_actions": list(value.required_actions),
    }


def encode_feature_change_evaluation(value: FeatureChangeEvaluation) -> dict[str, object]:
    return {
        "artifact_id": value.artifact_id,
        "derived_state": value.derived_state,
        "missing_requirements": list(value.missing_requirements),
        "failing_invariants": list(value.failing_invariants),
        "pending_invariants": list(value.pending_invariants),
        "obligation_intents": [
            encode_obligation_intent(intent) for intent in value.obligation_intents
        ],
        "promotion": encode_artifact_promotion_decision(value.promotion),
        "invalidation": encode_invalidation_record(value.invalidation),
    }


__all__ = [
    "encode_artifact_promotion_decision",
    "encode_feature_change_evaluation",
    "encode_invalidation_record",
]
