from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .artifact_evaluator import evaluate_feature_task_projection
from .artifact_projection import project_feature_task_record
from .artifact_snapshot import (
    build_feature_task_artifact_snapshot,
    evaluate_feature_task_artifact_snapshot_status,
    feature_task_artifact_snapshot_with_status,
    read_feature_task_artifact_snapshot,
)
from .obligation_runtime import build_feature_change_compiled_obligation_queue, read_feature_change_obligation_queue

FEATURE_TASK_ARTIFACT_RESOURCE_NAMES = frozenset(
    {
        "artifact-graph",
        "compiled-obligations",
        "slot-bindings",
        "verification-claims",
        "promotion-summary",
        "invalidation-summary",
    }
)


def is_feature_task_artifact_resource(resource_name: str) -> bool:
    return resource_name in FEATURE_TASK_ARTIFACT_RESOURCE_NAMES


def read_feature_task_artifact_resource(task: Mapping[str, object], task_dir: Path, resource_name: str) -> dict[str, object]:
    snapshot = read_feature_task_artifact_snapshot(task_dir)
    if snapshot is not None:
        snapshot_status = evaluate_feature_task_artifact_snapshot_status(snapshot, task=dict(task), task_dir=task_dir)
        snapshot = feature_task_artifact_snapshot_with_status(snapshot, snapshot_status)
    if snapshot is not None and resource_name == "artifact-graph":
        return snapshot
    if snapshot is not None and resource_name == "slot-bindings":
        return {
            "task_id": str(snapshot.get("task_id")),
            "feature_id": str(snapshot.get("feature_id")),
            "snapshot_status": snapshot["snapshot_status"],
            "slot_bindings": snapshot["slot_bindings"],
        }
    if snapshot is not None and resource_name == "verification-claims":
        return {
            "task_id": str(snapshot.get("task_id")),
            "feature_id": str(snapshot.get("feature_id")),
            "snapshot_status": snapshot["snapshot_status"],
            "claims": snapshot["verification_claims"],
        }
    if snapshot is not None and resource_name == "promotion-summary":
        evaluation = snapshot["evaluation"]
        return {
            "task_id": str(snapshot.get("task_id")),
            "feature_id": str(snapshot.get("feature_id")),
            "snapshot_status": snapshot["snapshot_status"],
            "promotion": evaluation["promotion"],
            "derived_state": evaluation["derived_state"],
        }
    if snapshot is not None and resource_name == "invalidation-summary":
        evaluation = snapshot["evaluation"]
        return {
            "task_id": str(snapshot.get("task_id")),
            "feature_id": str(snapshot.get("feature_id")),
            "snapshot_status": snapshot["snapshot_status"],
            "invalidation": evaluation["invalidation"],
            "derived_state": evaluation["derived_state"],
        }

    projection = project_feature_task_record(dict(task), task_dir)
    evaluation = evaluate_feature_task_projection(projection)

    if resource_name == "artifact-graph":
        return build_feature_task_artifact_snapshot(projection, evaluation)

    if resource_name == "compiled-obligations":
        persisted = read_feature_change_obligation_queue(task_dir)
        if persisted is not None:
            return persisted
        return build_feature_change_compiled_obligation_queue(projection, evaluation)

    if resource_name == "slot-bindings":
        return {
            "task_id": projection.task_id,
            "feature_id": projection.feature_id,
            "slot_bindings": projection.slot_bindings.to_dict(),
        }

    if resource_name == "verification-claims":
        return {
            "task_id": projection.task_id,
            "feature_id": projection.feature_id,
            "claims": [claim.to_dict() for claim in projection.verification_claims],
        }

    if resource_name == "promotion-summary":
        return {
            "task_id": projection.task_id,
            "feature_id": projection.feature_id,
            "promotion": evaluation.promotion.to_dict(),
            "derived_state": evaluation.derived_state,
        }

    if resource_name == "invalidation-summary":
        return {
            "task_id": projection.task_id,
            "feature_id": projection.feature_id,
            "invalidation": evaluation.invalidation.to_dict(),
            "derived_state": evaluation.derived_state,
        }

    raise ValueError(f"unsupported feature task artifact resource: {resource_name}")


__all__ = [
    "FEATURE_TASK_ARTIFACT_RESOURCE_NAMES",
    "is_feature_task_artifact_resource",
    "read_feature_task_artifact_resource",
]
