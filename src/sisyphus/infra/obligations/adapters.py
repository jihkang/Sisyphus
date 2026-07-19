from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ...application.results.obligations import (
    ObligationExecutionResult,
    ObligationQueueMaterialization,
)
from ...artifact_snapshot import materialize_feature_task_artifact_snapshot
from ..config.loader import SisyphusConfig
from .runtime import (
    execute_next_feature_change_obligation,
    materialize_feature_change_obligation_queue,
)


VerifyTask = Callable[[str], object]


class RepositoryObligationRuntimeAdapter:
    def __init__(
        self,
        repo_root: Path,
        config: SisyphusConfig,
        *,
        verify_task: VerifyTask,
    ) -> None:
        self._repo_root = repo_root
        self._config = config
        self._verify_task = verify_task

    def materialize_queue(self, task_id: str) -> ObligationQueueMaterialization:
        return materialize_feature_change_obligation_queue(
            self._repo_root,
            self._config,
            task_id,
        )

    def execute_next(self, task_id: str) -> ObligationExecutionResult:
        return execute_next_feature_change_obligation(
            self._repo_root,
            self._config,
            task_id,
            verify_task=self._verify_task,
        )

    def refresh_snapshot(self, task_id: str) -> bool:
        return materialize_feature_task_artifact_snapshot(
            self._repo_root,
            self._config,
            task_id,
        ).changed


__all__ = ["RepositoryObligationRuntimeAdapter", "VerifyTask"]
