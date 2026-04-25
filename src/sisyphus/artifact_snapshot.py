from __future__ import annotations

from dataclasses import dataclass
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


def build_feature_task_artifact_snapshot(
    projection: FeatureTaskArtifactProjection,
    evaluation: FeatureChangeEvaluation,
) -> dict[str, object]:
    return {
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


__all__ = [
    "DEFAULT_FEATURE_TASK_ARTIFACT_SNAPSHOT_PATH",
    "FEATURE_TASK_ARTIFACT_SNAPSHOT_SCHEMA_VERSION",
    "FeatureTaskArtifactSnapshotMaterialization",
    "build_feature_task_artifact_snapshot",
    "materialize_feature_task_artifact_snapshot",
    "materialize_feature_task_artifact_snapshot_record",
    "read_feature_task_artifact_snapshot",
]
