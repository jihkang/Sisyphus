from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ..application.artifact_resources import (
    FEATURE_TASK_ARTIFACT_RESOURCE_NAMES,
    FeatureArtifactResourceService,
    is_feature_task_artifact_resource,
)
from ..infra.artifacts.queries import RepositoryFeatureArtifactQueries


def build_feature_artifact_resource_service() -> FeatureArtifactResourceService:
    return FeatureArtifactResourceService(queries=RepositoryFeatureArtifactQueries())


def read_feature_task_artifact_resource(
    task: Mapping[str, object],
    task_dir: Path,
    resource_name: str,
) -> dict[str, object]:
    return build_feature_artifact_resource_service().read(task, task_dir, resource_name)


__all__ = [
    "FEATURE_TASK_ARTIFACT_RESOURCE_NAMES",
    "build_feature_artifact_resource_service",
    "is_feature_task_artifact_resource",
    "read_feature_task_artifact_resource",
]
