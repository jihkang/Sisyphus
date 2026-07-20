from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
from typing import Any

from ...application.artifacts.evaluation import evaluate_feature_task_projection
from ...application.artifacts.snapshot import (
    FeatureTaskArtifactSnapshotStatus,
    build_feature_task_artifact_snapshot,
    compare_feature_task_artifact_snapshot,
)
from ..config.loader import SisyphusConfig
from ..persistence.task_repository import load_task_record
from ..workspace.secure_files import SecureWorkspaceFiles
from .projection import project_feature_task_record


DEFAULT_FEATURE_TASK_ARTIFACT_SNAPSHOT_PATH = Path("artifacts") / "projection" / "feature-change.json"
_SNAPSHOT_RELATIVE = PurePosixPath(DEFAULT_FEATURE_TASK_ARTIFACT_SNAPSHOT_PATH.as_posix())
_MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class FeatureTaskArtifactSnapshotMaterialization:
    task_id: str
    snapshot_path: Path
    changed: bool


def materialize_feature_task_artifact_snapshot(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
) -> FeatureTaskArtifactSnapshotMaterialization:
    task, task_file = load_task_record(
        repo_root=repo_root,
        task_dir_name=config.task_dir,
        task_id=task_id,
    )
    return materialize_feature_task_artifact_snapshot_record(task=task, task_dir=task_file.parent)


def materialize_feature_task_artifact_snapshot_record(
    *,
    task: dict,
    task_dir: Path,
) -> FeatureTaskArtifactSnapshotMaterialization:
    projection = project_feature_task_record(task, task_dir)
    evaluation = evaluate_feature_task_projection(projection)
    payload = build_feature_task_artifact_snapshot(projection, evaluation)
    rendered = json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n"
    files = SecureWorkspaceFiles(task_dir)
    changed = files.write_text_atomic(_SNAPSHOT_RELATIVE, rendered)
    return FeatureTaskArtifactSnapshotMaterialization(
        task_id=projection.task_id,
        snapshot_path=task_dir / DEFAULT_FEATURE_TASK_ARTIFACT_SNAPSHOT_PATH,
        changed=changed,
    )


def read_feature_task_artifact_snapshot(task_dir: Path) -> dict[str, object] | None:
    try:
        rendered = SecureWorkspaceFiles(task_dir).read_text(
            _SNAPSHOT_RELATIVE,
            max_bytes=_MAX_SNAPSHOT_BYTES,
        )
    except FileNotFoundError:
        return None
    raw = json.loads(rendered)
    if not isinstance(raw, dict):
        snapshot_path = task_dir / DEFAULT_FEATURE_TASK_ARTIFACT_SNAPSHOT_PATH
        raise ValueError(f"feature task artifact snapshot must be an object: {snapshot_path}")
    return {str(key): value for key, value in raw.items()}


def evaluate_feature_task_artifact_snapshot_status(
    snapshot: dict[str, object],
    *,
    task: dict,
    task_dir: Path,
) -> FeatureTaskArtifactSnapshotStatus:
    fingerprint_value = snapshot.get("snapshot_fingerprint")
    fingerprint = str(fingerprint_value).strip() if fingerprint_value is not None else None
    try:
        projection = project_feature_task_record(task, task_dir)
        evaluation = evaluate_feature_task_projection(projection)
        current = build_feature_task_artifact_snapshot(projection, evaluation)
    except Exception as exc:
        return FeatureTaskArtifactSnapshotStatus(
            status="unavailable",
            fingerprint=fingerprint or None,
            reason=str(exc),
        )
    return compare_feature_task_artifact_snapshot(snapshot, current)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


__all__ = [
    "DEFAULT_FEATURE_TASK_ARTIFACT_SNAPSHOT_PATH",
    "FeatureTaskArtifactSnapshotMaterialization",
    "evaluate_feature_task_artifact_snapshot_status",
    "materialize_feature_task_artifact_snapshot",
    "materialize_feature_task_artifact_snapshot_record",
    "read_feature_task_artifact_snapshot",
]
