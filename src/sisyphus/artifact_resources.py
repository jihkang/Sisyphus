"""Backward-compatible artifact resource query imports."""

from .application.artifact_resources import (
    FEATURE_TASK_ARTIFACT_RESOURCE_NAMES,
    is_feature_task_artifact_resource,
)
from .composition.artifact_resources import read_feature_task_artifact_resource

__all__ = [
    "FEATURE_TASK_ARTIFACT_RESOURCE_NAMES",
    "is_feature_task_artifact_resource",
    "read_feature_task_artifact_resource",
]
