from __future__ import annotations

from dataclasses import dataclass

from ...domain.agent import AgentPolicyError
from ..commands.agent import RunTrackedAgentCommand
from ..results.agent import AgentExecutionResult
from .agent_execution import AgentExecutionError, AgentExecutionService
from .agents import AgentManagementError
from .planning import PlanningService


class AgentLaunchError(RuntimeError):
    pass


@dataclass(slots=True)
class AgentLaunchService:
    planning: PlanningService
    execution: AgentExecutionService

    def run(self, command: RunTrackedAgentCommand) -> AgentExecutionResult:
        if command.role == "worker":
            approved, task = self.planning.enforce_plan_approved(
                command.task_id,
                action="execution",
            )
            if not approved:
                raise AgentLaunchError(
                    _gate_message(
                        task,
                        source="plan",
                        fallback="task plan approval required before execution",
                    )
                )
            frozen, task = self.planning.enforce_spec_frozen(
                command.task_id,
                action="execution",
            )
            if not frozen:
                raise AgentLaunchError(
                    _gate_message(
                        task,
                        source="spec",
                        fallback="task spec must be frozen before execution",
                    )
                )
        try:
            return self.execution.run(command)
        except (AgentExecutionError, AgentManagementError, AgentPolicyError) as error:
            raise AgentLaunchError(str(error)) from error


def _gate_message(task: dict, *, source: str, fallback: str) -> str:
    gates = [gate for gate in task.get("gates", []) if gate.get("source") == source]
    return str(gates[0].get("message") or fallback) if gates else fallback


__all__ = ["AgentLaunchError", "AgentLaunchService"]
