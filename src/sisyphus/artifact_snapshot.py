"""Compatibility facade for feature artifact snapshots."""

from .application.artifacts.snapshot import (
    FEATURE_TASK_ARTIFACT_SNAPSHOT_SCHEMA_VERSION,
    FeatureTaskArtifactSnapshotStatus,
    build_feature_task_artifact_snapshot,
    feature_task_artifact_snapshot_with_status,
    fingerprint_feature_task_artifact_snapshot,
)
from .infra.artifacts.snapshot import (
    DEFAULT_FEATURE_TASK_ARTIFACT_SNAPSHOT_PATH,
    FeatureTaskArtifactSnapshotMaterialization,
    evaluate_feature_task_artifact_snapshot_status,
    materialize_feature_task_artifact_snapshot,
    materialize_feature_task_artifact_snapshot_record,
    read_feature_task_artifact_snapshot,
)

__all__ = [
    "DEFAULT_FEATURE_TASK_ARTIFACT_SNAPSHOT_PATH",
    "FEATURE_TASK_ARTIFACT_SNAPSHOT_SCHEMA_VERSION",
    "FeatureTaskArtifactSnapshotMaterialization",
    "FeatureTaskArtifactSnapshotStatus",
    "build_feature_task_artifact_snapshot",
    "evaluate_feature_task_artifact_snapshot_status",
    "feature_task_artifact_snapshot_with_status",
    "fingerprint_feature_task_artifact_snapshot",
    "materialize_feature_task_artifact_snapshot",
    "materialize_feature_task_artifact_snapshot_record",
    "read_feature_task_artifact_snapshot",
]
