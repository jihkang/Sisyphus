from __future__ import annotations

from dataclasses import dataclass

from ..ports.obligations import ObligationRuntimePort
from ..results.obligations import ObligationConvergenceResult


OBLIGATION_STATUS_BLOCKED = "blocked"
OBLIGATION_STATUS_FAILED = "failed"


@dataclass(slots=True)
class ObligationConvergenceService:
    runtime: ObligationRuntimePort

    def converge(self, task_id: str, *, max_steps: int = 8) -> ObligationConvergenceResult:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")

        progressed = False
        executed_count = 0
        last_status = "idle"
        for step in range(1, max_steps + 1):
            # Queue materialization must observe stale inputs before snapshot refresh.
            queue = self.runtime.materialize_queue(task_id)
            progressed = progressed or queue.changed

            execution = self.runtime.execute_next(task_id)
            snapshot_changed = self.runtime.refresh_snapshot(task_id)
            progressed = progressed or snapshot_changed
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


__all__ = ["ObligationConvergenceService"]
