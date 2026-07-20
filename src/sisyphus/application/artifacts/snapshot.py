from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from ..codecs.artifact_evaluation import encode_feature_change_evaluation
from ..codecs.artifacts import (
    encode_artifact_record,
    encode_feature_change_slot_bindings,
    encode_task_run_ref,
    encode_verification_claim,
)
from ...domain.artifact.evaluation import FeatureChangeEvaluation
from .projection import FeatureTaskArtifactProjection


FEATURE_TASK_ARTIFACT_SNAPSHOT_SCHEMA_VERSION = "sisyphus.feature_task_artifact_snapshot.v1"


@dataclass(frozen=True, slots=True)
class FeatureTaskArtifactSnapshotStatus:
    status: str
    fingerprint: str | None
    current_fingerprint: str | None = None
    reason: str | None = None


def build_feature_task_artifact_snapshot(
    projection: FeatureTaskArtifactProjection,
    evaluation: FeatureChangeEvaluation,
) -> dict[str, object]:
    from ..codecs.artifact_snapshots import encode_feature_task_artifact_snapshot_status

    payload: dict[str, object] = {
        "schema_version": FEATURE_TASK_ARTIFACT_SNAPSHOT_SCHEMA_VERSION,
        "task_id": projection.task_id,
        "feature_id": projection.feature_id,
        "source_artifact_id": projection.feature_change_artifact.artifact_id,
        "composite": encode_artifact_record(projection.feature_change_artifact),
        "artifacts": {
            "spec": encode_artifact_record(projection.spec_artifact),
            "implementation": encode_artifact_record(projection.implementation_artifact),
            "tests": [encode_artifact_record(item) for item in projection.test_artifacts],
            "execution_receipts": [
                encode_artifact_record(item) for item in projection.execution_receipts
            ],
        },
        "slot_bindings": encode_feature_change_slot_bindings(projection.slot_bindings),
        "verification_claims": [
            encode_verification_claim(item) for item in projection.verification_claims
        ],
        "task_runs": [encode_task_run_ref(item) for item in projection.task_run_refs],
        "evaluation": encode_feature_change_evaluation(evaluation),
    }
    fingerprint = fingerprint_feature_task_artifact_snapshot(payload)
    return {
        **payload,
        "snapshot_fingerprint": fingerprint,
        "snapshot_status": encode_feature_task_artifact_snapshot_status(
            FeatureTaskArtifactSnapshotStatus(
                status="current",
                fingerprint=fingerprint,
                current_fingerprint=fingerprint,
            )
        ),
    }


def compare_feature_task_artifact_snapshot(
    snapshot: dict[str, object],
    current: dict[str, object],
) -> FeatureTaskArtifactSnapshotStatus:
    fingerprint = _optional_string(snapshot.get("snapshot_fingerprint"))
    current_fingerprint = _optional_string(current.get("snapshot_fingerprint"))
    if fingerprint is not None and fingerprint == current_fingerprint:
        return FeatureTaskArtifactSnapshotStatus(
            status="current",
            fingerprint=fingerprint,
            current_fingerprint=current_fingerprint,
        )
    return FeatureTaskArtifactSnapshotStatus(
        status="stale",
        fingerprint=fingerprint,
        current_fingerprint=current_fingerprint,
    )


def feature_task_artifact_snapshot_with_status(
    snapshot: dict[str, object],
    status: FeatureTaskArtifactSnapshotStatus,
) -> dict[str, object]:
    from ..codecs.artifact_snapshots import encode_feature_task_artifact_snapshot_status

    return {
        **snapshot,
        "snapshot_status": encode_feature_task_artifact_snapshot_status(status),
    }


def fingerprint_feature_task_artifact_snapshot(snapshot: dict[str, object]) -> str:
    payload = {
        key: value
        for key, value in snapshot.items()
        if key not in {"snapshot_fingerprint", "snapshot_status"}
    }
    rendered = json.dumps(_json_safe(payload), separators=(",", ":"), sort_keys=True)
    return f"sha256:{hashlib.sha256(rendered.encode('utf-8')).hexdigest()}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


__all__ = [
    "FEATURE_TASK_ARTIFACT_SNAPSHOT_SCHEMA_VERSION",
    "FeatureTaskArtifactSnapshotStatus",
    "build_feature_task_artifact_snapshot",
    "compare_feature_task_artifact_snapshot",
    "feature_task_artifact_snapshot_with_status",
    "fingerprint_feature_task_artifact_snapshot",
]
