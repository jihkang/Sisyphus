"""Compatibility facade for feature artifact projection."""

from .application.artifacts.projection import FeatureTaskArtifactProjection
from .infra.artifacts.projection import project_feature_task, project_feature_task_record

__all__ = [
    "FeatureTaskArtifactProjection",
    "project_feature_task",
    "project_feature_task_record",
]
