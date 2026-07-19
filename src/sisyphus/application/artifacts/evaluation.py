from __future__ import annotations

from collections.abc import Mapping, Sequence

from ...domain.artifact.evaluation import (
    FeatureChangeEvaluation,
    FeatureChangePolicy,
    evaluate_typed_feature_change_artifact,
)
from ...domain.artifact.models import (
    ArtifactRecord,
    CompositeArtifactRecord,
    FeatureChangeSlotBindings,
    VerificationClaimRecord,
)
from ..codecs.artifacts import (
    decode_feature_change_slot_bindings,
    decode_verification_claim,
)
from .projection import FeatureTaskArtifactProjection


def evaluate_feature_task_projection(
    projection: FeatureTaskArtifactProjection,
    *,
    policy: FeatureChangePolicy | None = None,
) -> FeatureChangeEvaluation:
    return evaluate_typed_feature_change_artifact(
        projection.feature_change_artifact,
        slot_bindings=projection.slot_bindings,
        verification_claims=projection.verification_claims,
        artifacts=projection.atomic_artifacts(),
        policy=policy,
    )


def evaluate_feature_change_artifact(
    feature_change_artifact: CompositeArtifactRecord,
    *,
    slot_bindings: FeatureChangeSlotBindings | None = None,
    verification_claims: Sequence[VerificationClaimRecord] | None = None,
    artifacts: Sequence[ArtifactRecord] = (),
    policy: FeatureChangePolicy | None = None,
) -> FeatureChangeEvaluation:
    resolved_bindings = slot_bindings or _slot_bindings_from_payload(feature_change_artifact)
    resolved_claims = tuple(
        verification_claims or _verification_claims_from_payload(feature_change_artifact)
    )
    return evaluate_typed_feature_change_artifact(
        feature_change_artifact,
        slot_bindings=resolved_bindings,
        verification_claims=resolved_claims,
        artifacts=artifacts,
        policy=policy,
    )


def _slot_bindings_from_payload(
    feature_change_artifact: CompositeArtifactRecord,
) -> FeatureChangeSlotBindings:
    raw = feature_change_artifact.payload.get("slot_bindings")
    if not isinstance(raw, Mapping):
        raise ValueError("feature_change.payload.slot_bindings is required for evaluation")
    return decode_feature_change_slot_bindings(raw)


def _verification_claims_from_payload(
    feature_change_artifact: CompositeArtifactRecord,
) -> tuple[VerificationClaimRecord, ...]:
    raw = feature_change_artifact.payload.get("verification_claims", [])
    if not isinstance(raw, list):
        raise TypeError("feature_change.payload.verification_claims must be a list")
    claims: list[VerificationClaimRecord] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise TypeError(
                f"feature_change.payload.verification_claims[{index}] must be a mapping"
            )
        claims.append(decode_verification_claim(item))
    return tuple(claims)


__all__ = ["evaluate_feature_change_artifact", "evaluate_feature_task_projection"]
