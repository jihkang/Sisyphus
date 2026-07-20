"""Compatibility facade for feature artifact evaluation."""

from .application.codecs.artifact_evaluation import (
    encode_artifact_promotion_decision,
    encode_feature_change_evaluation,
    encode_invalidation_record,
)
from .application.artifacts.evaluation import (
    evaluate_feature_change_artifact,
    evaluate_feature_task_projection,
)
from .domain.artifact.evaluation import (
    INVALIDATION_STATUS_FRESH,
    INVALIDATION_STATUS_INVALID,
    INVALIDATION_STATUS_STALE,
    ArtifactPromotionDecision,
    FeatureChangeEvaluation,
    FeatureChangePolicy,
    InvalidationRecord,
    PromotionDecision,
)
from .compat.serialization import install_serialization_compat


install_serialization_compat(
    ArtifactPromotionDecision,
    encode_mapping=encode_artifact_promotion_decision,
)
install_serialization_compat(
    InvalidationRecord,
    encode_mapping=encode_invalidation_record,
)
install_serialization_compat(
    FeatureChangeEvaluation,
    encode_mapping=encode_feature_change_evaluation,
)

__all__ = [
    "ArtifactPromotionDecision",
    "FeatureChangeEvaluation",
    "FeatureChangePolicy",
    "INVALIDATION_STATUS_FRESH",
    "INVALIDATION_STATUS_INVALID",
    "INVALIDATION_STATUS_STALE",
    "InvalidationRecord",
    "PromotionDecision",
    "evaluate_feature_change_artifact",
    "evaluate_feature_task_projection",
]
