from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .artifact_evaluator import FeatureChangeEvaluation, evaluate_feature_task_projection
from .artifact_projection import FeatureTaskArtifactProjection, project_feature_task_record
from .config import SisyphusConfig
from .state import load_task_record


FEATURE_TASK_ARTIFACT_SNAPSHOT_SCHEMA_VERSION = "sisyphus.feature_task_artifact_snapshot.v1"
DEFAULT_FEATURE_TASK_ARTIFACT_SNAPSHOT_PATH = Path("artifacts") / "projection" / "feature-change.json"


@dataclass(frozen=True, slots=True)
class FeatureTaskArtifactSnapshotMaterialization:
    task_id: str
    snapshot_path: Path
    changed: bool


@dataclass(frozen=True, slots=True)
class FeatureTaskArtifactSnapshotStatus:
    status: str
    fingerprint: str | None
    current_fingerprint: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {"status": self.status}
        if self.fingerprint is not None:
            data["fingerprint"] = self.fingerprint
        if self.current_fingerprint is not None:
            data["current_fingerprint"] = self.current_fingerprint
        if self.reason is not None:
            data["reason"] = self.reason
        return data


def build_feature_task_artifact_snapshot(
    projection: FeatureTaskArtifactProjection,
    evaluation: FeatureChangeEvaluation,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": FEATURE_TASK_ARTIFACT_SNAPSHOT_SCHEMA_VERSION,
        "task_id": projection.task_id,
        "feature_id": projection.feature_id,
        "source_artifact_id": projection.feature_change_artifact.artifact_id,
        "composite": projection.feature_change_artifact.to_dict(),
        "artifacts": {
            "spec": projection.spec_artifact.to_dict(),
            "implementation": projection.implementation_artifact.to_dict(),
            "tests": [artifact.to_dict() for artifact in projection.test_artifacts],
            "execution_receipts": [artifact.to_dict() for artifact in projection.execution_receipts],
        },
        "slot_bindings": projection.slot_bindings.to_dict(),
        "verification_claims": [claim.to_dict() for claim in projection.verification_claims],
        "task_runs": [run.to_dict() for run in projection.task_run_refs],
        "evaluation": evaluation.to_dict(),
    }
    fingerprint = fingerprint_feature_task_artifact_snapshot(payload)
    return {
        **payload,
        "snapshot_fingerprint": fingerprint,
        "snapshot_status": FeatureTaskArtifactSnapshotStatus(
            status="current",
            fingerprint=fingerprint,
            current_fingerprint=fingerprint,
        ).to_dict(),
    }


def materialize_feature_task_artifact_snapshot(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
) -> FeatureTaskArtifactSnapshotMaterialization:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    return materialize_feature_task_artifact_snapshot_record(task=task, task_dir=task_file.parent)


def materialize_feature_task_artifact_snapshot_record(
    *,
    task: dict,
    task_dir: Path,
) -> FeatureTaskArtifactSnapshotMaterialization:
    projection = project_feature_task_record(task, task_dir)
    evaluation = evaluate_feature_task_projection(projection)
    payload = build_feature_task_artifact_snapshot(projection, evaluation)
    snapshot_path = task_dir / DEFAULT_FEATURE_TASK_ARTIFACT_SNAPSHOT_PATH
    changed = _write_json_if_changed(snapshot_path, payload)
    return FeatureTaskArtifactSnapshotMaterialization(
        task_id=projection.task_id,
        snapshot_path=snapshot_path,
        changed=changed,
    )


def read_feature_task_artifact_snapshot(task_dir: Path) -> dict[str, object] | None:
    snapshot_path = task_dir / DEFAULT_FEATURE_TASK_ARTIFACT_SNAPSHOT_PATH
    if not snapshot_path.exists():
        return None
    raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"feature task artifact snapshot must be an object: {snapshot_path}")
    return {str(key): value for key, value in raw.items()}


def evaluate_feature_task_artifact_snapshot_status(
    snapshot: dict[str, object],
    *,
    task: dict,
    task_dir: Path,
) -> FeatureTaskArtifactSnapshotStatus:
    fingerprint = _optional_string(snapshot.get("snapshot_fingerprint"))
    try:
        projection = project_feature_task_record(task, task_dir)
        evaluation = evaluate_feature_task_projection(projection)
        current = build_feature_task_artifact_snapshot(projection, evaluation)
    except Exception as exc:
        return FeatureTaskArtifactSnapshotStatus(
            status="unavailable",
            fingerprint=fingerprint,
            reason=str(exc),
        )
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
    return {**snapshot, "snapshot_status": status.to_dict()}


def fingerprint_feature_task_artifact_snapshot(snapshot: dict[str, object]) -> str:
    payload = {
        key: value
        for key, value in snapshot.items()
        if key not in {"snapshot_fingerprint", "snapshot_status"}
    }
    rendered = json.dumps(_json_safe(payload), separators=(",", ":"), sort_keys=True)
    return f"sha256:{hashlib.sha256(rendered.encode('utf-8')).hexdigest()}"


def _write_json_if_changed(path: Path, payload: dict[str, object]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return False
    path.write_text(rendered, encoding="utf-8")
    return True


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
