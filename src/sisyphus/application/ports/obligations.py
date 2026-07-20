from __future__ import annotations

from typing import Protocol

from ..results.obligations import ObligationExecutionResult, ObligationQueueMaterialization


class ObligationRuntimePort(Protocol):
    def materialize_queue(self, task_id: str) -> ObligationQueueMaterialization: ...

    def execute_next(self, task_id: str) -> ObligationExecutionResult: ...

    def refresh_snapshot(self, task_id: str) -> bool: ...


__all__ = ["ObligationRuntimePort"]
