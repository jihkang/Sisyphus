from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .ports.artifact_queries import FeatureArtifactQueryPort, FeatureArtifactReadModel


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


@dataclass(slots=True)
class FeatureArtifactResourceService:
    queries: FeatureArtifactQueryPort

    def read(
        self,
        task: Mapping[str, object],
        task_dir: Path,
        resource_name: str,
    ) -> dict[str, object]:
        if not is_feature_task_artifact_resource(resource_name):
            raise ValueError(f"unsupported feature task artifact resource: {resource_name}")

        snapshot = self.queries.read_snapshot(task, task_dir)
        snapshot_resource = _snapshot_resource(snapshot, resource_name)
        if snapshot_resource is not None:
            return snapshot_resource

        current = self.queries.project_current(
            task,
            task_dir,
            include_compiled_obligations=resource_name == "compiled-obligations",
        )
        return self._current_resource(current, task_dir, resource_name)

    def _current_resource(
        self,
        current: FeatureArtifactReadModel,
        task_dir: Path,
        resource_name: str,
    ) -> dict[str, object]:
        if resource_name == "artifact-graph":
            return dict(current.artifact_graph)

        if resource_name == "compiled-obligations":
            persisted = self.queries.read_compiled_obligations(task_dir)
            if persisted is not None:
                return dict(persisted)
            if current.compiled_obligations is None:
                raise RuntimeError("artifact query did not compile requested obligations")
            return dict(current.compiled_obligations)

        if resource_name == "slot-bindings":
            return {
                "task_id": current.task_id,
                "feature_id": current.feature_id,
                "slot_bindings": dict(current.slot_bindings),
            }

        if resource_name == "verification-claims":
            return {
                "task_id": current.task_id,
                "feature_id": current.feature_id,
                "claims": [dict(claim) for claim in current.verification_claims],
            }

        if resource_name == "promotion-summary":
            return {
                "task_id": current.task_id,
                "feature_id": current.feature_id,
                "promotion": dict(current.promotion),
                "derived_state": current.derived_state,
            }

        if resource_name == "invalidation-summary":
            return {
                "task_id": current.task_id,
                "feature_id": current.feature_id,
                "invalidation": dict(current.invalidation),
                "derived_state": current.derived_state,
            }

        raise ValueError(f"unsupported feature task artifact resource: {resource_name}")


def _snapshot_resource(
    snapshot: Mapping[str, object] | None,
    resource_name: str,
) -> dict[str, object] | None:
    if snapshot is None or resource_name == "compiled-obligations":
        return None
    if resource_name == "artifact-graph":
        return dict(snapshot)

    task_id = str(snapshot.get("task_id"))
    feature_id = str(snapshot.get("feature_id"))
    snapshot_status = snapshot["snapshot_status"]
    if resource_name == "slot-bindings":
        return {
            "task_id": task_id,
            "feature_id": feature_id,
            "snapshot_status": snapshot_status,
            "slot_bindings": snapshot["slot_bindings"],
        }
    if resource_name == "verification-claims":
        return {
            "task_id": task_id,
            "feature_id": feature_id,
            "snapshot_status": snapshot_status,
            "claims": snapshot["verification_claims"],
        }

    evaluation = snapshot["evaluation"]
    if not isinstance(evaluation, Mapping):
        raise TypeError("artifact snapshot evaluation must be an object")
    if resource_name == "promotion-summary":
        return {
            "task_id": task_id,
            "feature_id": feature_id,
            "snapshot_status": snapshot_status,
            "promotion": evaluation["promotion"],
            "derived_state": evaluation["derived_state"],
        }
    if resource_name == "invalidation-summary":
        return {
            "task_id": task_id,
            "feature_id": feature_id,
            "snapshot_status": snapshot_status,
            "invalidation": evaluation["invalidation"],
            "derived_state": evaluation["derived_state"],
        }
    return None


__all__ = [
    "FEATURE_TASK_ARTIFACT_RESOURCE_NAMES",
    "FeatureArtifactResourceService",
    "is_feature_task_artifact_resource",
]
