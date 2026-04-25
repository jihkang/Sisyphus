from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .artifact_evaluator import FeatureChangeEvaluation, evaluate_feature_task_projection
from .artifact_projection import FeatureTaskArtifactProjection, project_feature_task_record
from .config import SisyphusConfig
from .feature_change_dsl import (
    compile_feature_change_obligations,
    default_feature_change_protocol_spec,
    obligation_intents_from_feature_change_evaluation,
)
from .state import load_task_record


COMPILED_OBLIGATION_QUEUE_SCHEMA_VERSION = "sisyphus.compiled_obligation_queue.v1"
DEFAULT_COMPILED_OBLIGATION_QUEUE_PATH = Path("artifacts") / "obligations" / "compiled.json"


@dataclass(frozen=True, slots=True)
class ObligationQueueMaterialization:
    task_id: str
    queue_path: Path
    changed: bool
    obligation_count: int


def build_feature_change_compiled_obligation_queue(
    projection: FeatureTaskArtifactProjection,
    evaluation: FeatureChangeEvaluation,
) -> dict[str, object]:
    protocol = default_feature_change_protocol_spec()
    intents = obligation_intents_from_feature_change_evaluation(evaluation)
    compiled = compile_feature_change_obligations(intents, projection, protocol=protocol)
    return {
        "schema_version": COMPILED_OBLIGATION_QUEUE_SCHEMA_VERSION,
        "task_id": projection.task_id,
        "feature_id": projection.feature_id,
        "source_artifact_id": projection.feature_change_artifact.artifact_id,
        "protocol": protocol.to_dict(),
        "evaluation": evaluation.to_dict(),
        "intents": [intent.to_dict() for intent in intents],
        "compiled_obligations": [obligation.to_dict() for obligation in compiled],
        "obligation_count": len(compiled),
    }


def materialize_feature_change_obligation_queue(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
) -> ObligationQueueMaterialization:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    return materialize_feature_change_obligation_queue_record(task=task, task_dir=task_file.parent)


def materialize_feature_change_obligation_queue_record(
    *,
    task: dict,
    task_dir: Path,
) -> ObligationQueueMaterialization:
    projection = project_feature_task_record(task, task_dir)
    evaluation = evaluate_feature_task_projection(projection)
    payload = build_feature_change_compiled_obligation_queue(projection, evaluation)
    queue_path = task_dir / DEFAULT_COMPILED_OBLIGATION_QUEUE_PATH
    changed = _write_json_if_changed(queue_path, payload)
    return ObligationQueueMaterialization(
        task_id=projection.task_id,
        queue_path=queue_path,
        changed=changed,
        obligation_count=int(payload["obligation_count"]),
    )


def read_feature_change_obligation_queue(task_dir: Path) -> dict[str, object] | None:
    queue_path = task_dir / DEFAULT_COMPILED_OBLIGATION_QUEUE_PATH
    if not queue_path.exists():
        return None
    raw = json.loads(queue_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"compiled obligation queue must be an object: {queue_path}")
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
    "COMPILED_OBLIGATION_QUEUE_SCHEMA_VERSION",
    "DEFAULT_COMPILED_OBLIGATION_QUEUE_PATH",
    "ObligationQueueMaterialization",
    "build_feature_change_compiled_obligation_queue",
    "materialize_feature_change_obligation_queue",
    "materialize_feature_change_obligation_queue_record",
    "read_feature_change_obligation_queue",
]
