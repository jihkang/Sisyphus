from __future__ import annotations

from pathlib import Path
import unittest

from sisyphus.application.results.obligations import (
    ObligationConvergenceResult,
    ObligationExecutionResult,
    ObligationQueueMaterialization,
)
from sisyphus.application.use_cases.obligations import ObligationConvergenceService
from sisyphus.obligation_runtime import ObligationConvergenceResult as PublicConvergenceResult


class RuntimeFake:
    def __init__(
        self,
        executions: list[ObligationExecutionResult],
        *,
        queue_changes: list[bool] | None = None,
        snapshot_changes: list[bool] | None = None,
        fail_execution: bool = False,
    ) -> None:
        self.executions = list(executions)
        self.queue_changes = list(queue_changes or [False] * max(len(executions), 1))
        self.snapshot_changes = list(snapshot_changes or [False] * max(len(executions), 1))
        self.fail_execution = fail_execution
        self.calls: list[str] = []

    def materialize_queue(self, task_id: str) -> ObligationQueueMaterialization:
        self.calls.append("queue")
        return ObligationQueueMaterialization(
            task_id=task_id,
            queue_path=Path("compiled.json"),
            changed=self.queue_changes.pop(0),
            obligation_count=len(self.executions),
        )

    def execute_next(self, task_id: str) -> ObligationExecutionResult:
        self.calls.append("execute")
        if self.fail_execution:
            raise RuntimeError("execution failed")
        return self.executions.pop(0)

    def refresh_snapshot(self, task_id: str) -> bool:
        self.calls.append("snapshot")
        return self.snapshot_changes.pop(0)


class ObligationApplicationTests(unittest.TestCase):
    def test_public_result_preserves_canonical_identity(self) -> None:
        self.assertIs(PublicConvergenceResult, ObligationConvergenceResult)

    def test_idle_runtime_converges_in_queue_execute_snapshot_order(self) -> None:
        runtime = RuntimeFake([_execution(executed=False, status="idle")])

        result = ObligationConvergenceService(runtime).converge("TF-1")

        self.assertTrue(result.converged)
        self.assertFalse(result.progressed)
        self.assertEqual(result.step_count, 1)
        self.assertEqual(result.executed_count, 0)
        self.assertEqual(runtime.calls, ["queue", "execute", "snapshot"])

    def test_pass_then_idle_reprojects_before_next_iteration(self) -> None:
        runtime = RuntimeFake(
            [
                _execution(executed=True, status="passed"),
                _execution(executed=False, status="idle"),
            ],
            queue_changes=[False, False],
            snapshot_changes=[True, False],
        )

        result = ObligationConvergenceService(runtime).converge("TF-1")

        self.assertTrue(result.converged)
        self.assertTrue(result.progressed)
        self.assertEqual(result.step_count, 2)
        self.assertEqual(result.executed_count, 1)
        self.assertEqual(
            runtime.calls,
            ["queue", "execute", "snapshot", "queue", "execute", "snapshot"],
        )

    def test_blocked_execution_stops_after_snapshot_refresh(self) -> None:
        runtime = RuntimeFake([_execution(executed=True, status="blocked", message="policy")])

        result = ObligationConvergenceService(runtime).converge("TF-1")

        self.assertFalse(result.converged)
        self.assertTrue(result.progressed)
        self.assertEqual(result.executed_count, 1)
        self.assertEqual(result.message, "policy")
        self.assertEqual(runtime.calls, ["queue", "execute", "snapshot"])

    def test_step_limit_returns_nonconverged_receipt(self) -> None:
        runtime = RuntimeFake(
            [
                _execution(executed=True, status="passed"),
                _execution(executed=True, status="passed"),
            ]
        )

        result = ObligationConvergenceService(runtime).converge("TF-1", max_steps=2)

        self.assertFalse(result.converged)
        self.assertEqual(result.step_count, 2)
        self.assertEqual(result.executed_count, 2)
        self.assertEqual(result.message, "maximum obligation convergence steps reached")

    def test_invalid_step_limit_has_no_runtime_effect(self) -> None:
        runtime = RuntimeFake([_execution(executed=False, status="idle")])

        with self.assertRaisesRegex(ValueError, "max_steps must be positive"):
            ObligationConvergenceService(runtime).converge("TF-1", max_steps=0)

        self.assertEqual(runtime.calls, [])

    def test_execution_exception_does_not_refresh_snapshot(self) -> None:
        runtime = RuntimeFake(
            [_execution(executed=False, status="idle")],
            fail_execution=True,
        )

        with self.assertRaisesRegex(RuntimeError, "execution failed"):
            ObligationConvergenceService(runtime).converge("TF-1")

        self.assertEqual(runtime.calls, ["queue", "execute"])


def _execution(
    *,
    executed: bool,
    status: str,
    message: str | None = None,
) -> ObligationExecutionResult:
    return ObligationExecutionResult(
        task_id="TF-1",
        obligation_id="obligation-1" if executed else None,
        executed=executed,
        status=status,
        queue_path=Path("compiled.json"),
        message=message,
    )


if __name__ == "__main__":
    unittest.main()
