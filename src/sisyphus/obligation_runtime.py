from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .artifact_evaluator import FeatureChangeEvaluation, evaluate_feature_task_projection
from .artifact_projection import FeatureTaskArtifactProjection, project_feature_task_record
from .artifact_snapshot import (
    evaluate_feature_task_artifact_snapshot_status,
    materialize_feature_task_artifact_snapshot,
    read_feature_task_artifact_snapshot,
)
from .config import SisyphusConfig
from .dsl import ObligationIntent
from .feature_change_dsl import (
    compile_feature_change_obligations,
    default_feature_change_protocol_spec,
    obligation_intents_from_feature_change_evaluation,
)
from .execution_policy import (
    EXECUTION_RUNNER_SISYPHUS_VERIFY,
    execution_policy_receipt_fields,
    execution_policy_registry_to_dict,
    resolve_execution_policy,
)
from .state import load_task_record, utc_now


COMPILED_OBLIGATION_QUEUE_SCHEMA_VERSION = "sisyphus.compiled_obligation_queue.v1"
DEFAULT_COMPILED_OBLIGATION_QUEUE_PATH = Path("artifacts") / "obligations" / "compiled.json"
OBLIGATION_STATUS_PENDING = "pending"
OBLIGATION_STATUS_RUNNING = "running"
OBLIGATION_STATUS_PASSED = "passed"
OBLIGATION_STATUS_FAILED = "failed"
OBLIGATION_STATUS_BLOCKED = "blocked"

_VERIFY_OBLIGATION_SPECS = frozenset(
    {
        "verify_local_feature",
        "verify_cross_feature",
        "verify_composite_feature",
        "reverify_required_claims",
        "reverify_stale_inputs",
    }
)


@dataclass(frozen=True, slots=True)
class ObligationQueueMaterialization:
    task_id: str
    queue_path: Path
    changed: bool
    obligation_count: int


@dataclass(frozen=True, slots=True)
class ObligationExecutionResult:
    task_id: str
    obligation_id: str | None
    executed: bool
    status: str
    queue_path: Path
    message: str | None = None


@dataclass(frozen=True, slots=True)
class ObligationConvergenceResult:
    task_id: str
    progressed: bool
    converged: bool
    step_count: int
    executed_count: int
    last_status: str
    message: str | None = None


def build_feature_change_compiled_obligation_queue(
    projection: FeatureTaskArtifactProjection,
    evaluation: FeatureChangeEvaluation,
    *,
    additional_intents: tuple[ObligationIntent, ...] = (),
) -> dict[str, object]:
    protocol = default_feature_change_protocol_spec()
    intents = _merge_obligation_intents(
        obligation_intents_from_feature_change_evaluation(evaluation),
        additional_intents,
    )
    compiled = compile_feature_change_obligations(intents, projection, protocol=protocol)
    return {
        "schema_version": COMPILED_OBLIGATION_QUEUE_SCHEMA_VERSION,
        "task_id": projection.task_id,
        "feature_id": projection.feature_id,
        "source_artifact_id": projection.feature_change_artifact.artifact_id,
        "protocol": protocol.to_dict(),
        "execution_policies": execution_policy_registry_to_dict(),
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
    snapshot_status, snapshot_intents = _snapshot_invalidation_obligation_intents(
        task=task,
        task_dir=task_dir,
        projection=projection,
    )
    payload = build_feature_change_compiled_obligation_queue(
        projection,
        evaluation,
        additional_intents=snapshot_intents,
    )
    if snapshot_status is not None:
        payload["snapshot_status"] = snapshot_status
    queue_path = task_dir / DEFAULT_COMPILED_OBLIGATION_QUEUE_PATH
    previous = read_feature_change_obligation_queue(task_dir)
    if previous is not None:
        payload = _merge_existing_obligation_state(payload, previous)
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


def execute_next_feature_change_obligation(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
) -> ObligationExecutionResult:
    materialized = materialize_feature_change_obligation_queue(repo_root=repo_root, config=config, task_id=task_id)
    queue = read_feature_change_obligation_queue(materialized.queue_path.parent.parent.parent)
    if queue is None:
        return ObligationExecutionResult(
            task_id=task_id,
            obligation_id=None,
            executed=False,
            status="idle",
            queue_path=materialized.queue_path,
            message="compiled obligation queue is not available",
        )

    obligations = _queue_obligations(queue)
    selected_index = next(
        (
            index
            for index, obligation in enumerate(obligations)
            if str(obligation.get("status") or OBLIGATION_STATUS_PENDING) == OBLIGATION_STATUS_PENDING
        ),
        None,
    )
    if selected_index is None:
        return ObligationExecutionResult(
            task_id=task_id,
            obligation_id=None,
            executed=False,
            status="idle",
            queue_path=materialized.queue_path,
            message="no pending compiled obligation",
        )

    obligation = obligations[selected_index]
    obligation_id = str(obligation.get("id") or "")
    spec_ref = str(obligation.get("spec_ref") or "")
    execution_policy_ref = _obligation_execution_policy_ref(obligation)
    execution_policy = resolve_execution_policy(execution_policy_ref)
    if execution_policy is None:
        receipt = {
            "status": OBLIGATION_STATUS_BLOCKED,
            "finished_at": utc_now(),
            "spec_ref": spec_ref,
            "execution_policy_ref": execution_policy_ref or "",
            "reason": "execution policy not found",
        }
        _update_queue_obligation(queue=queue, index=selected_index, status=OBLIGATION_STATUS_BLOCKED, receipt=receipt)
        _write_json_if_changed(materialized.queue_path, queue)
        return ObligationExecutionResult(
            task_id=task_id,
            obligation_id=obligation_id,
            executed=True,
            status=OBLIGATION_STATUS_BLOCKED,
            queue_path=materialized.queue_path,
            message=f"execution policy not found: {execution_policy_ref or '<none>'}",
        )

    policy_receipt = execution_policy_receipt_fields(execution_policy)
    _update_queue_obligation(
        queue=queue,
        index=selected_index,
        status=OBLIGATION_STATUS_RUNNING,
        receipt={
            "status": OBLIGATION_STATUS_RUNNING,
            "started_at": utc_now(),
            "spec_ref": spec_ref,
            **policy_receipt,
        },
    )
    _write_json_if_changed(materialized.queue_path, queue)

    if spec_ref in _VERIFY_OBLIGATION_SPECS and execution_policy.runner == EXECUTION_RUNNER_SISYPHUS_VERIFY:
        from .audit import run_verify

        outcome = run_verify(repo_root=repo_root, config=config, task_id=task_id)
        status = OBLIGATION_STATUS_PASSED if outcome.status == "passed" else OBLIGATION_STATUS_FAILED
        receipt = {
            "status": status,
            "finished_at": utc_now(),
            "spec_ref": spec_ref,
            **policy_receipt,
            "verify_status": outcome.status,
            "verify_stage": outcome.stage,
            "gate_count": len(outcome.gates),
            "command_count": len(outcome.command_results),
            "verify_file": str(outcome.verify_file),
        }
        _update_queue_obligation(queue=queue, index=selected_index, status=status, receipt=receipt)
        _write_json_if_changed(materialized.queue_path, queue)
        return ObligationExecutionResult(
            task_id=task_id,
            obligation_id=obligation_id,
            executed=True,
            status=status,
            queue_path=materialized.queue_path,
        )

    receipt = {
        "status": OBLIGATION_STATUS_BLOCKED,
        "finished_at": utc_now(),
        "spec_ref": spec_ref,
        **policy_receipt,
        "reason": "unsupported compiled obligation runner",
    }
    _update_queue_obligation(queue=queue, index=selected_index, status=OBLIGATION_STATUS_BLOCKED, receipt=receipt)
    _write_json_if_changed(materialized.queue_path, queue)
    return ObligationExecutionResult(
        task_id=task_id,
        obligation_id=obligation_id,
        executed=True,
        status=OBLIGATION_STATUS_BLOCKED,
        queue_path=materialized.queue_path,
        message=f"unsupported compiled obligation runner: {execution_policy.runner} for {spec_ref}",
    )


def converge_feature_change_obligations(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    max_steps: int = 8,
) -> ObligationConvergenceResult:
    if max_steps < 1:
        raise ValueError("max_steps must be positive")

    progressed = False
    executed_count = 0
    last_status = "idle"
    for step in range(1, max_steps + 1):
        # Build obligations before refreshing the persisted snapshot; otherwise a stale snapshot
        # can be overwritten before it regenerates invalidation repair work.
        queue = materialize_feature_change_obligation_queue(repo_root=repo_root, config=config, task_id=task_id)
        progressed = progressed or queue.changed

        execution = execute_next_feature_change_obligation(repo_root=repo_root, config=config, task_id=task_id)
        snapshot = materialize_feature_task_artifact_snapshot(repo_root=repo_root, config=config, task_id=task_id)
        progressed = progressed or snapshot.changed
        last_status = execution.status
        if not execution.executed:
            return ObligationConvergenceResult(
                task_id=task_id,
                progressed=progressed,
                converged=True,
                step_count=step,
                executed_count=executed_count,
                last_status=last_status,
                message=execution.message,
            )

        progressed = True
        executed_count += 1
        if execution.status in {OBLIGATION_STATUS_BLOCKED, OBLIGATION_STATUS_FAILED}:
            return ObligationConvergenceResult(
                task_id=task_id,
                progressed=True,
                converged=False,
                step_count=step,
                executed_count=executed_count,
                last_status=last_status,
                message=execution.message,
            )

    return ObligationConvergenceResult(
        task_id=task_id,
        progressed=progressed,
        converged=False,
        step_count=max_steps,
        executed_count=executed_count,
        last_status=last_status,
        message="maximum obligation convergence steps reached",
    )


def _write_json_if_changed(path: Path, payload: dict[str, object]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return False
    path.write_text(rendered, encoding="utf-8")
    return True


def _merge_existing_obligation_state(payload: dict[str, object], previous: dict[str, object]) -> dict[str, object]:
    previous_by_key: dict[tuple[str, str], dict[str, object]] = {}
    for obligation in _queue_obligations(previous):
        key = _obligation_state_key(obligation)
        if key is not None:
            previous_by_key[key] = obligation

    for obligation in _queue_obligations(payload):
        key = _obligation_state_key(obligation)
        if key is None:
            continue
        previous_obligation = previous_by_key.get(key)
        if previous_obligation is None:
            continue
        for field_name in ("status", "execution_receipts"):
            if field_name in previous_obligation:
                obligation[field_name] = previous_obligation[field_name]
    return payload


def _snapshot_invalidation_obligation_intents(
    *,
    task: dict,
    task_dir: Path,
    projection: FeatureTaskArtifactProjection,
) -> tuple[dict[str, object] | None, tuple[ObligationIntent, ...]]:
    snapshot = read_feature_task_artifact_snapshot(task_dir)
    if snapshot is None:
        return None, ()
    status = evaluate_feature_task_artifact_snapshot_status(snapshot, task=task, task_dir=task_dir).to_dict()
    if status.get("status") != "stale":
        return status, ()
    fingerprint = str(status.get("fingerprint") or "")
    current_fingerprint = str(status.get("current_fingerprint") or "")
    return status, (
        ObligationIntent(
            intent_kind="reverify_stale_inputs",
            target_artifact=f"artifact://{projection.feature_change_artifact.artifact_id}",
            reasons=("snapshot_stale",),
            data={
                "required_action": "reverify_stale_inputs",
                "stale_source": "feature_task_artifact_snapshot",
                "snapshot_fingerprint": fingerprint,
                "current_fingerprint": current_fingerprint,
            },
        ),
    )


def _merge_obligation_intents(
    base: tuple[ObligationIntent, ...],
    additional: tuple[ObligationIntent, ...],
) -> tuple[ObligationIntent, ...]:
    merged = list(base)
    seen = {(intent.intent_kind, intent.target_artifact) for intent in merged}
    for intent in additional:
        key = (intent.intent_kind, intent.target_artifact)
        if key in seen:
            continue
        seen.add(key)
        merged.append(intent)
    return tuple(merged)


def _obligation_state_key(obligation: dict[str, object]) -> tuple[str, str] | None:
    obligation_id = str(obligation.get("id") or "")
    materialized = obligation.get("materialized_input_set")
    if not obligation_id or not isinstance(materialized, dict):
        return None
    fingerprint = str(materialized.get("fingerprint") or "")
    if not fingerprint:
        return None
    return (obligation_id, fingerprint)


def _obligation_execution_policy_ref(obligation: dict[str, object]) -> str | None:
    value = obligation.get("execution_policy_ref")
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _queue_obligations(queue: dict[str, object]) -> list[dict[str, object]]:
    raw = queue.get("compiled_obligations", [])
    if not isinstance(raw, list):
        raise ValueError("compiled obligation queue must contain a list of compiled_obligations")
    obligations: list[dict[str, object]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"compiled_obligations[{index}] must be an object")
        obligations.append(item)
    return obligations


def _update_queue_obligation(
    *,
    queue: dict[str, object],
    index: int,
    status: str,
    receipt: dict[str, object],
) -> None:
    obligations = _queue_obligations(queue)
    obligation = obligations[index]
    receipts = obligation.get("execution_receipts", [])
    if not isinstance(receipts, list):
        receipts = []
    obligation["status"] = status
    obligation["execution_receipts"] = [*receipts, receipt]
    queue["compiled_obligations"] = obligations


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


__all__ = [
    "COMPILED_OBLIGATION_QUEUE_SCHEMA_VERSION",
    "DEFAULT_COMPILED_OBLIGATION_QUEUE_PATH",
    "OBLIGATION_STATUS_BLOCKED",
    "OBLIGATION_STATUS_FAILED",
    "OBLIGATION_STATUS_PASSED",
    "OBLIGATION_STATUS_PENDING",
    "OBLIGATION_STATUS_RUNNING",
    "ObligationConvergenceResult",
    "ObligationExecutionResult",
    "ObligationQueueMaterialization",
    "build_feature_change_compiled_obligation_queue",
    "converge_feature_change_obligations",
    "execute_next_feature_change_obligation",
    "materialize_feature_change_obligation_queue",
    "materialize_feature_change_obligation_queue_record",
    "read_feature_change_obligation_queue",
]
