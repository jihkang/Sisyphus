from __future__ import annotations

from pathlib import Path

from .application.results.obligations import (
    ObligationConvergenceResult,
    ObligationExecutionResult,
    ObligationQueueMaterialization,
)
from .composition.obligations import build_obligation_convergence_service
from .composition.verification import build_verification_service
from .infra.config.loader import SisyphusConfig
from .infra.obligations.runtime import (
    COMPILED_OBLIGATION_QUEUE_SCHEMA_VERSION,
    DEFAULT_COMPILED_OBLIGATION_QUEUE_PATH,
    OBLIGATION_STATUS_BLOCKED,
    OBLIGATION_STATUS_FAILED,
    OBLIGATION_STATUS_PASSED,
    OBLIGATION_STATUS_PENDING,
    OBLIGATION_STATUS_RUNNING,
    build_feature_change_compiled_obligation_queue,
    execute_next_feature_change_obligation as _execute_next,
    materialize_feature_change_obligation_queue,
    materialize_feature_change_obligation_queue_record,
    read_feature_change_obligation_queue,
)


def execute_next_feature_change_obligation(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
) -> ObligationExecutionResult:
    verification = build_verification_service(repo_root, config)
    return _execute_next(
        repo_root,
        config,
        task_id,
        verify_task=verification.verify,
    )


def converge_feature_change_obligations(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    max_steps: int = 8,
) -> ObligationConvergenceResult:
    return build_obligation_convergence_service(repo_root, config).converge(
        task_id,
        max_steps=max_steps,
    )


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
