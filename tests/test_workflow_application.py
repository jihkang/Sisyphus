from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from sisyphus.application.ports.workflow import (  # noqa: E402
    CloseoutResult,
    ConformanceCheck,
    ProviderRequest,
    VerificationResult,
    WorkflowEvent,
)
from sisyphus.application.use_cases.workflow import WorkflowService  # noqa: E402


class MemoryTasks:
    def __init__(self, task: dict) -> None:
        self.task = deepcopy(task)
        self.save_count = 0

    def load(self, task_id: str) -> dict:
        if task_id != self.task["id"]:
            raise KeyError(task_id)
        return self.task

    def save(self, task: dict) -> None:
        self.task = task
        self.save_count += 1

    def update(self, task_id: str, mutator) -> dict:
        if task_id != self.task["id"]:
            raise KeyError(task_id)
        replacement = mutator(self.task)
        if replacement is not None:
            self.task = replacement
        return self.task


class PlanningFake:
    def __init__(self) -> None:
        self.frozen: list[str] = []
        self.generated: list[str] = []

    def freeze_spec(self, task_id: str) -> None:
        self.frozen.append(task_id)

    def generate_subtasks(self, task_id: str) -> None:
        self.generated.append(task_id)


class ObligationsFake:
    def __init__(self, progressed: bool = False) -> None:
        self.progressed = progressed
        self.calls: list[str] = []

    def converge(self, task_id: str) -> bool:
        self.calls.append(task_id)
        return self.progressed


class ConformanceFake:
    def __init__(self, *, pre: str = "green", post: str = "green") -> None:
        self.pre = pre
        self.post = post
        self.log_writes = 0

    def pre_execution(self, task: dict, *, subtask_id: str, source: str) -> ConformanceCheck:
        return ConformanceCheck(self.pre, f"pre:{source}:{subtask_id}")

    def post_execution(
        self,
        task: dict,
        *,
        subtask_id: str,
        exit_code: int,
        source: str,
    ) -> ConformanceCheck:
        return ConformanceCheck(self.post, f"post:{source}:{subtask_id}:{exit_code}")

    def execution_contract(self, task: dict, subtask: dict[str, object]) -> str:
        return f"contract:{subtask['id']}"

    def write_log(self, task: dict) -> None:
        self.log_writes += 1

    def status(self, task: dict) -> str:
        return "green"


class ProviderFake:
    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self.requests: list[ProviderRequest] = []

    def run(self, request: ProviderRequest) -> int:
        self.requests.append(request)
        return self.exit_code


class VerificationFake:
    def __init__(self, *, gates: tuple[dict[str, object], ...] = ()) -> None:
        self.gates = gates
        self.calls: list[str] = []

    def verify(self, task_id: str) -> VerificationResult:
        self.calls.append(task_id)
        return VerificationResult(gates=self.gates)


class CloseoutFake:
    def __init__(self, *, closed: bool = True) -> None:
        self.closed = closed
        self.calls: list[tuple[str, bool]] = []

    def close(self, task_id: str, *, allow_dirty: bool) -> CloseoutResult:
        self.calls.append((task_id, allow_dirty))
        return CloseoutResult(closed=self.closed)


class EventsFake:
    def __init__(self) -> None:
        self.events: list[WorkflowEvent] = []

    def publish(self, event: WorkflowEvent) -> None:
        self.events.append(event)


class InterventionsFake:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def required(self, **request: str) -> None:
        self.calls.append(request)


class WorkflowApplicationTests(unittest.TestCase):
    def test_pending_plan_does_not_run_any_effect(self) -> None:
        service, dependencies = _service(_task(plan_status="pending_review"))

        self.assertFalse(service.advance("TF-1"))
        self.assertEqual(dependencies["planning"].frozen, [])
        self.assertEqual(dependencies["provider"].requests, [])
        self.assertEqual(dependencies["events"].events, [])

    def test_approved_draft_spec_requests_automatic_freeze(self) -> None:
        service, dependencies = _service(_task(spec_status="draft"))

        self.assertTrue(service.advance("TF-1"))
        self.assertEqual(dependencies["planning"].frozen, ["TF-1"])
        self.assertEqual(dependencies["planning"].generated, [])

    def test_feature_obligation_progress_precedes_subtask_generation(self) -> None:
        service, dependencies = _service(
            _task(task_type="feature", subtasks=[]),
            obligation_progressed=True,
        )

        self.assertTrue(service.advance("TF-1"))
        self.assertEqual(dependencies["obligations"].calls, ["TF-1"])
        self.assertEqual(dependencies["planning"].generated, [])

    def test_queued_subtask_runs_provider_and_emits_events_in_order(self) -> None:
        service, dependencies = _service(_task())

        self.assertTrue(service.advance("TF-1"))

        self.assertEqual(dependencies["tasks"].task["subtasks"][0]["status"], "completed")
        request = dependencies["provider"].requests[0]
        self.assertEqual(request.provider, "codex")
        self.assertEqual(request.agent_id, "subtask-001")
        self.assertIn("contract:subtask-001", request.instruction)
        self.assertEqual(dependencies["conformance"].log_writes, 2)
        self.assertEqual(
            [event.event_type for event in dependencies["events"].events],
            [
                "conformance.pre_exec.green",
                "subtask.started",
                "conformance.post_exec.green",
                "subtask.completed",
            ],
        )

    def test_red_pre_execution_check_blocks_without_running_provider(self) -> None:
        service, dependencies = _service(_task(), pre_conformance="red")

        self.assertTrue(service.advance("TF-1"))

        self.assertEqual(dependencies["tasks"].task["subtasks"][0]["status"], "failed")
        self.assertEqual(dependencies["tasks"].task["workflow_phase"], "needs_user_input")
        self.assertEqual(dependencies["provider"].requests, [])
        self.assertEqual(len(dependencies["interventions"].calls), 1)

    def test_completed_subtasks_verify_then_close(self) -> None:
        completed = _task(subtasks=[{**_subtask(), "status": "completed"}])
        service, dependencies = _service(completed)

        self.assertTrue(service.advance("TF-1"))

        self.assertEqual(dependencies["verification"].calls, ["TF-1"])
        self.assertEqual(dependencies["closeout"].calls, [("TF-1", True)])
        self.assertEqual(dependencies["tasks"].task["workflow_phase"], "closed")
        self.assertEqual(
            [event.data["workflow_phase"] for event in dependencies["events"].events],
            ["integration_review", "closed"],
        )

    def test_verification_gates_pause_before_close(self) -> None:
        completed = _task(subtasks=[{**_subtask(), "status": "completed"}])
        service, dependencies = _service(
            completed,
            verification_gates=({"code": "VERIFY_FAILED"},),
        )

        self.assertTrue(service.advance("TF-1"))

        self.assertEqual(dependencies["closeout"].calls, [])
        self.assertEqual(dependencies["tasks"].task["workflow_phase"], "needs_user_input")
        self.assertEqual(len(dependencies["interventions"].calls), 1)


def _service(
    task: dict,
    *,
    obligation_progressed: bool = False,
    pre_conformance: str = "green",
    post_conformance: str = "green",
    provider_exit_code: int = 0,
    verification_gates: tuple[dict[str, object], ...] = (),
) -> tuple[WorkflowService, dict[str, object]]:
    dependencies = {
        "tasks": MemoryTasks(task),
        "planning": PlanningFake(),
        "obligations": ObligationsFake(obligation_progressed),
        "conformance": ConformanceFake(pre=pre_conformance, post=post_conformance),
        "provider": ProviderFake(provider_exit_code),
        "verification": VerificationFake(gates=verification_gates),
        "closeout": CloseoutFake(),
        "events": EventsFake(),
        "interventions": InterventionsFake(),
    }
    return WorkflowService(**dependencies), dependencies


def _task(
    *,
    task_type: str = "issue",
    plan_status: str = "approved",
    spec_status: str = "frozen",
    subtasks: list[dict] | None = None,
) -> dict:
    return {
        "id": "TF-1",
        "type": task_type,
        "status": "open",
        "workflow_phase": "execution",
        "plan_status": plan_status,
        "spec_status": spec_status,
        "subtasks": [_subtask()] if subtasks is None else subtasks,
        "meta": {"auto_loop_enabled": True, "default_provider": "codex"},
    }


def _subtask() -> dict:
    return {
        "id": "subtask-001",
        "title": "Implement behavior",
        "category": "normal",
        "status": "queued",
    }


if __name__ == "__main__":
    unittest.main()
