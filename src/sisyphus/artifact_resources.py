from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .artifact_evaluator import evaluate_feature_task_projection
from .artifact_projection import project_feature_task_record

FEATURE_TASK_ARTIFACT_RESOURCE_NAMES = frozenset(
    {
        "artifact-graph",
        "slot-bindings",
        "verification-claims",
        "promotion-summary",
        "invalidation-summary",
    }
)


def is_feature_task_artifact_resource(resource_name: str) -> bool:
    return resource_name in FEATURE_TASK_ARTIFACT_RESOURCE_NAMES


def read_feature_task_artifact_resource(task: Mapping[str, object], task_dir: Path, resource_name: str) -> dict[str, object]:
    projection = project_feature_task_record(dict(task), task_dir)
    evaluation = evaluate_feature_task_projection(projection)

    if resource_name == "artifact-graph":
        return {
            "task_id": projection.task_id,
            "feature_id": projection.feature_id,
            "composite": projection.feature_change_artifact.to_dict(),
            "artifacts": {
                "spec": projection.spec_artifact.to_dict(),
                "implementation": projection.implementation_artifact.to_dict(),
                "tests": [artifact.to_dict() for artifact in projection.test_artifacts],
                "execution_receipts": [artifact.to_dict() for artifact in projection.execution_receipts],
            },
            "verification_claims": [claim.to_dict() for claim in projection.verification_claims],
            "task_runs": [run.to_dict() for run in projection.task_run_refs],
            "evaluation": evaluation.to_dict(),
        }

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
