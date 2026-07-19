"""Compatibility facade for feature artifact evaluation."""

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
