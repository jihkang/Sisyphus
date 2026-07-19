from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from sisyphus.application.commands.agent import RunTrackedAgentCommand  # noqa: E402
from sisyphus.application.ports.agent_execution import (  # noqa: E402
    ProcessExecution,
    ProcessStartError,
)
from sisyphus.application.use_cases.agent_execution import (  # noqa: E402
    AgentExecutionError,
    AgentExecutionService,
)


class TrackingFake:
    def __init__(self, *, heartbeat_ok: bool = True) -> None:
        self.heartbeat_ok = heartbeat_ok
        self.registrations = []
        self.updates = []
        self.heartbeats = []

    def register(self, registration) -> None:
        self.registrations.append(registration)

    def update(self, update) -> None:
        self.updates.append(update)

    def heartbeat(self, update) -> bool:
        self.heartbeats.append(update)
        return self.heartbeat_ok


class ProcessFake:
    def __init__(
        self,
        *,
        exit_code: int = 0,
        summary: str | None = "done",
        error: BaseException | None = None,
    ) -> None:
        self.exit_code = exit_code
        self.summary = summary
        self.error = error
        self.requests = []

    def run(self, request, observer) -> ProcessExecution:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        observer.started(4242)
        observer.heartbeat("working")
        return ProcessExecution(exit_code=self.exit_code, output_summary=self.summary)


class AgentExecutionApplicationTests(unittest.TestCase):
    def test_success_tracks_start_heartbeat_and_completion(self) -> None:
        service, tracking, process = _service()

        result = service.run(_command())

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(tracking.registrations[0].current_step, "running python -m worker")
        self.assertEqual(tracking.updates[0].pid, 4242)
        self.assertEqual(tracking.heartbeats[0].last_message_summary, "working")
        self.assertEqual(tracking.updates[-1].status, "completed")
        self.assertEqual(tracking.updates[-1].last_message_summary, "done")
        self.assertEqual(process.requests[0].env, (("TOKEN", "value"),))

    def test_failed_exit_records_retryable_agent_failure(self) -> None:
        service, tracking, _ = _service(exit_code=7, summary=None)

        result = service.run(_command())

        self.assertEqual(result.status, "failed")
        self.assertEqual(tracking.updates[-1].error, "command exited with code 7")
        self.assertEqual(
            tracking.updates[-1].last_message_summary,
            "wrapper failed with exit code 7",
        )

    def test_process_start_error_marks_agent_failed_and_preserves_cause(self) -> None:
        service, tracking, _ = _service(error=ProcessStartError("missing binary"))

        with self.assertRaisesRegex(AgentExecutionError, "missing binary"):
            service.run(_command())

        self.assertEqual(tracking.updates[-1].status, "failed")
        self.assertEqual(tracking.updates[-1].error, "missing binary")

    def test_keyboard_interrupt_marks_agent_cancelled(self) -> None:
        service, tracking, _ = _service(error=KeyboardInterrupt())

        with self.assertRaises(KeyboardInterrupt):
            service.run(_command())

        self.assertEqual(tracking.updates[-1].status, "cancelled")
        self.assertEqual(tracking.updates[-1].error, "cancelled by operator")

    def test_empty_command_is_rejected_before_registration(self) -> None:
        service, tracking, process = _service()

        with self.assertRaisesRegex(AgentExecutionError, "requires a command"):
            service.run(_command(command=()))

        self.assertEqual(tracking.registrations, [])
        self.assertEqual(process.requests, [])


def _service(
    *,
    exit_code: int = 0,
    summary: str | None = "done",
    error: BaseException | None = None,
) -> tuple[AgentExecutionService, TrackingFake, ProcessFake]:
    tracking = TrackingFake()
    process = ProcessFake(exit_code=exit_code, summary=summary, error=error)
    return AgentExecutionService(tracking=tracking, processes=process), tracking, process


def _command(*, command: tuple[str, ...] = ("python", "-m", "worker")) -> RunTrackedAgentCommand:
    return RunTrackedAgentCommand(
        task_id="TF-1",
        agent_id="worker-1",
        role="worker",
        provider="codex",
        command=command,
        run_cwd="/workspace",
        env=(("TOKEN", "value"),),
    )


if __name__ == "__main__":
    unittest.main()
