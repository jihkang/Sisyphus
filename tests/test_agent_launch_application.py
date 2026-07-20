from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from sisyphus.application.commands.agent import RunTrackedAgentCommand  # noqa: E402
from sisyphus.application.results.agent import AgentExecutionResult  # noqa: E402
from sisyphus.application.use_cases.agent_launch import (  # noqa: E402
    AgentLaunchError,
    AgentLaunchService,
)


class PlanningFake:
    def __init__(self, *, plan: bool = True, spec: bool = True) -> None:
        self.plan = plan
        self.spec = spec
        self.calls: list[str] = []

    def enforce_plan_approved(self, task_id: str, *, action: str):
        self.calls.append("plan")
        return self.plan, {
            "gates": []
            if self.plan
            else [{"source": "plan", "message": "plan review required"}]
        }

    def enforce_spec_frozen(self, task_id: str, *, action: str):
        self.calls.append("spec")
        return self.spec, {
            "gates": []
            if self.spec
            else [{"source": "spec", "message": "spec freeze required"}]
        }


class ExecutionFake:
    def __init__(self) -> None:
        self.commands = []

    def run(self, command: RunTrackedAgentCommand) -> AgentExecutionResult:
        self.commands.append(command)
        return AgentExecutionResult(
            task_id=command.task_id,
            agent_id=command.agent_id,
            exit_code=0,
            status="completed",
        )


class AgentLaunchApplicationTests(unittest.TestCase):
    def test_worker_requires_plan_before_spec_or_process(self) -> None:
        planning = PlanningFake(plan=False)
        execution = ExecutionFake()
        service = AgentLaunchService(planning=planning, execution=execution)

        with self.assertRaisesRegex(AgentLaunchError, "plan review required"):
            service.run(_command())

        self.assertEqual(planning.calls, ["plan"])
        self.assertEqual(execution.commands, [])

    def test_worker_requires_frozen_spec_before_process(self) -> None:
        planning = PlanningFake(spec=False)
        execution = ExecutionFake()
        service = AgentLaunchService(planning=planning, execution=execution)

        with self.assertRaisesRegex(AgentLaunchError, "spec freeze required"):
            service.run(_command())

        self.assertEqual(planning.calls, ["plan", "spec"])
        self.assertEqual(execution.commands, [])

    def test_worker_executes_after_both_gates_pass(self) -> None:
        planning = PlanningFake()
        execution = ExecutionFake()
        service = AgentLaunchService(planning=planning, execution=execution)

        result = service.run(_command())

        self.assertEqual(result.status, "completed")
        self.assertEqual(planning.calls, ["plan", "spec"])
        self.assertEqual(len(execution.commands), 1)

    def test_non_worker_role_does_not_apply_worker_execution_gates(self) -> None:
        planning = PlanningFake(plan=False, spec=False)
        execution = ExecutionFake()
        service = AgentLaunchService(planning=planning, execution=execution)

        result = service.run(_command(role="reviewer"))

        self.assertEqual(result.status, "completed")
        self.assertEqual(planning.calls, [])


def _command(*, role: str = "worker") -> RunTrackedAgentCommand:
    return RunTrackedAgentCommand(
        task_id="TF-1",
        agent_id="worker-1",
        role=role,
        provider="codex",
        command=("python", "-m", "worker"),
    )


if __name__ == "__main__":
    unittest.main()
