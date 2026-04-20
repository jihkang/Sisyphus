from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .artifact_evaluator import (
    CURRENT_FEATURE_CHANGE_DERIVED_STATES,
    CURRENT_FEATURE_CHANGE_RESERVED_STATES,
    CURRENT_FEATURE_CHANGE_VERIFICATION_SCOPES,
    evaluate_feature_task_projection,
)
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


def _projection_metadata() -> dict[str, object]:
    return {
        "authority_source": "task_runtime",
        "projection_model": "derived_feature_task_projection",
        "projection_status": "partial_runtime_support",
        "source_of_truth": ["task.json", "task_docs", "verify_receipts"],
        "supported_verification_scopes": list(CURRENT_FEATURE_CHANGE_VERIFICATION_SCOPES),
        "derived_states": list(CURRENT_FEATURE_CHANGE_DERIVED_STATES),
        "reserved_states": list(CURRENT_FEATURE_CHANGE_RESERVED_STATES),
    }


def read_feature_task_artifact_resource(task: Mapping[str, object], task_dir: Path, resource_name: str) -> dict[str, object]:
    projection = project_feature_task_record(dict(task), task_dir)
    evaluation = evaluate_feature_task_projection(projection)

    if resource_name == "artifact-graph":
        return {
            "projection": _projection_metadata(),
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
            "projection": _projection_metadata(),
            "task_id": projection.task_id,
            "feature_id": projection.feature_id,
            "slot_bindings": projection.slot_bindings.to_dict(),
        }

    if resource_name == "verification-claims":
        return {
            "projection": _projection_metadata(),
            "task_id": projection.task_id,
            "feature_id": projection.feature_id,
            "claims": [claim.to_dict() for claim in projection.verification_claims],
        }

    if resource_name == "promotion-summary":
        return {
            "projection": _projection_metadata(),
            "task_id": projection.task_id,
            "feature_id": projection.feature_id,
            "promotion": evaluation.promotion.to_dict(),
            "derived_state": evaluation.derived_state,
        }

    if resource_name == "invalidation-summary":
        return {
            "projection": _projection_metadata(),
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
