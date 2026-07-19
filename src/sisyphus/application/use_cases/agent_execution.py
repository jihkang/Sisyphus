from __future__ import annotations

from dataclasses import dataclass

from ...domain.agent import AgentPolicyError
from ..commands.agent import RegisterAgentCommand, RunTrackedAgentCommand, UpdateAgentCommand
from ..ports.agent_execution import (
    AgentProcessPort,
    AgentTrackingPort,
    ProcessExecutionRequest,
    ProcessStartError,
)
from ..results.agent import AgentExecutionResult
from .agents import AgentManagementError


class AgentExecutionError(RuntimeError):
    pass


@dataclass(slots=True)
class AgentExecutionService:
    tracking: AgentTrackingPort
    processes: AgentProcessPort

    def run(self, command: RunTrackedAgentCommand) -> AgentExecutionResult:
        if not command.command:
            raise AgentExecutionError("agent run requires a command after `--`")
        step = command.current_step or f"running {' '.join(command.command)}"
        initial_summary = command.last_message_summary or f"{command.provider} wrapper started"
        self.tracking.register(
            RegisterAgentCommand(
                task_id=command.task_id,
                agent_id=command.agent_id,
                role=command.role,
                provider=command.provider,
                current_step=step,
                last_message_summary=initial_summary,
                owned_paths=command.owned_paths,
                command=command.command,
            )
        )
        observer = _TrackingObserver(
            tracking=self.tracking,
            command=command,
            current_step=step,
            initial_summary=initial_summary,
        )
        try:
            execution = self.processes.run(
                ProcessExecutionRequest(
                    command=command.command,
                    cwd=command.run_cwd or ".",
                    stdin_text=command.stdin_text,
                    env=command.env,
                    heartbeat_seconds=command.heartbeat_seconds,
                ),
                observer,
            )
        except ProcessStartError as error:
            self.tracking.update(
                observer.update(
                    status="failed",
                    error=str(error),
                    last_message_summary=str(error),
                )
            )
            raise AgentExecutionError(str(error)) from error
        except KeyboardInterrupt:
            self.tracking.update(
                observer.update(
                    status="cancelled",
                    error="cancelled by operator",
                    last_message_summary="cancelled by operator",
                )
            )
            raise

        status = "completed" if execution.exit_code == 0 else "failed"
        error = None if execution.exit_code == 0 else f"command exited with code {execution.exit_code}"
        final_summary = execution.output_summary or (
            "wrapper finished successfully"
            if execution.exit_code == 0
            else f"wrapper failed with exit code {execution.exit_code}"
        )
        self.tracking.update(
            observer.update(
                status=status,
                error=error,
                last_message_summary=final_summary,
            )
        )
        return AgentExecutionResult(
            task_id=command.task_id,
            agent_id=command.agent_id,
            exit_code=execution.exit_code,
            status=status,
        )


@dataclass(slots=True)
class _TrackingObserver:
    tracking: AgentTrackingPort
    command: RunTrackedAgentCommand
    current_step: str
    initial_summary: str

    def started(self, pid: int) -> None:
        self.tracking.update(self.update(pid=pid, last_message_summary=self.initial_summary))

    def heartbeat(self, output_summary: str | None) -> bool:
        try:
            self.tracking.update(
                self.update(last_message_summary=output_summary or self.initial_summary)
            )
        except (AgentManagementError, AgentPolicyError, FileNotFoundError):
            return False
        return True

    def update(
        self,
        *,
        status: str | None = None,
        error: str | None = None,
        last_message_summary: str | None = None,
        pid: int | None = None,
    ) -> UpdateAgentCommand:
        return UpdateAgentCommand(
            task_id=self.command.task_id,
            agent_id=self.command.agent_id,
            status=status,
            provider=self.command.provider,
            command=self.command.command,
            current_step=self.current_step,
            last_message_summary=last_message_summary,
            pid=pid,
            error=error,
        )


__all__ = ["AgentExecutionError", "AgentExecutionService"]
