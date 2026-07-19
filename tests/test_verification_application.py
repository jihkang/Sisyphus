from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from sisyphus.application.results.artifacts import ArtifactRef  # noqa: E402
from sisyphus.application.use_cases.verification import VerificationService  # noqa: E402
from sisyphus.domain.lifecycle import ConformanceState  # noqa: E402
from sisyphus.domain.verification import CommandExecution, VerificationStatus  # noqa: E402


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
        replacement = mutator(self.task)
        if replacement is not None:
            self.task = replacement
        return self.task


class PlanningDocumentsFake:
    def sync_strategy(self, task_id: str, task: dict) -> dict:
        return task


class DocumentsFake:
    def __init__(self) -> None:
        self.contents = {
            "BRIEF.md": "# Brief\n\n- [x] Explicit criterion\n",
            "PLAN.md": "# Plan\n\nComplete\n",
        }
        self.writes: list[tuple[str, str]] = []

    def read(self, task_id: str, relative_path: str) -> str | None:
        return self.contents.get(relative_path)

    def write(self, task_id: str, relative_path: str, content: str) -> ArtifactRef:
        self.writes.append((relative_path, content))
        self.contents[relative_path] = content
        return ArtifactRef(relative_path=relative_path)


class ValidationFake:
    def __init__(self, gates: tuple[dict, ...] = ()) -> None:
        self.gates = gates

    def required(self, task_id: str, task: dict) -> bool:
        return True

    def collect_gates(self, task_id: str, task: dict, **kwargs) -> tuple[dict, ...]:
        return self.gates


class ConformanceFake:
    def __init__(self) -> None:
        self.appended: list[dict[str, object]] = []

    def snapshot(self, task: dict) -> ConformanceState:
        return ConformanceState()

    def append(self, task: dict, **entry) -> dict:
        self.appended.append(entry)
        return task


class CommandsFake:
    def __init__(self, status: VerificationStatus = VerificationStatus.PASSED) -> None:
        self.status = status
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def run(self, task_id: str, commands: tuple[str, ...]) -> tuple[CommandExecution, ...]:
        self.calls.append((task_id, commands))
        if not commands:
            return ()
        exit_code = 0 if self.status == VerificationStatus.PASSED else 1
        return (
            CommandExecution(
                name=commands[0],
                command=commands[0],
                status=self.status,
                exit_code=exit_code,
                started_at="2026-07-19T12:00:00Z",
                finished_at="2026-07-19T12:00:00Z",
                duration_ms=None,
                output_excerpt="ok" if exit_code == 0 else "failed",
            ),
        )


class EvidenceFake:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def write(self, task_id: str, task: dict, command_results: tuple[CommandExecution, ...]) -> None:
        self.calls.append((task_id, len(command_results)))


class EventsFake:
    def __init__(self) -> None:
        self.events = []

    def publish(self, event) -> None:
        self.events.append(event)


class FixedClock:
    def now(self) -> str:
        return "2026-07-19T12:00:00Z"


class VerificationApplicationTests(unittest.TestCase):
    def test_lifecycle_gate_blocks_before_commands_and_evidence(self) -> None:
        service, dependencies = _service(_task(plan_status="pending_review"))

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.stage, "plan_review")
        self.assertEqual(outcome.audit_attempts, 0)
        self.assertEqual(dependencies["commands"].calls, [])
        self.assertEqual(dependencies["evidence"].calls, [])
        self.assertEqual(dependencies["documents"].writes[0][0], "VERIFY.md")

    def test_successful_command_produces_typed_receipt_and_verified_state(self) -> None:
        service, dependencies = _service(_task())

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "passed")
        self.assertEqual(outcome.stage, "done")
        self.assertEqual(outcome.verify_artifact, ArtifactRef("VERIFY.md"))
        self.assertEqual(outcome.command_results[0].status, VerificationStatus.PASSED)
        task = dependencies["tasks"].task
        self.assertEqual(task["workflow_phase"], "verified")
        self.assertEqual(task["last_verify_results"][0]["exit_code"], 0)
        self.assertEqual(dependencies["evidence"].calls, [("TF-1", 1)])
        self.assertEqual(dependencies["events"].events[0].event_type, "verify.completed")

    def test_failed_command_adds_verify_gate(self) -> None:
        service, dependencies = _service(
            _task(),
            command_status=VerificationStatus.FAILED,
        )

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "failed")
        self.assertIn("VERIFY_FAILED", {gate["code"] for gate in outcome.gates})
        self.assertEqual(dependencies["tasks"].task["status"], "blocked")

    def test_spec_validation_gate_skips_command_execution(self) -> None:
        gate = {
            "code": "SPEC_VALIDATION_STALE",
            "message": "stale",
            "blocking": True,
            "source": "spec_validation",
            "created_at": "2026-07-19T12:00:00Z",
        }
        service, dependencies = _service(_task(), validation_gates=(gate,))

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.stage, "spec")
        self.assertEqual(dependencies["commands"].calls, [])
        self.assertEqual(dependencies["tasks"].task["workflow_phase"], "spec_in_review")

    def test_underdesigned_task_reopens_plan(self) -> None:
        task = _task()
        task["design"] = {
            "mode": "none",
            "layer_impact": "layer-adding",
        }
        service, dependencies = _service(task)

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "failed")
        self.assertEqual(dependencies["tasks"].task["plan_status"], "changes_requested")
        self.assertEqual(dependencies["tasks"].task["spec_status"], "draft")
        self.assertIn("DESIGN_REPLAN_REQUIRED", {gate["code"] for gate in outcome.gates})
        self.assertEqual(dependencies["conformance"].appended[0]["status"], "yellow")


def _service(
    task: dict,
    *,
    command_status: VerificationStatus = VerificationStatus.PASSED,
    validation_gates: tuple[dict, ...] = (),
) -> tuple[VerificationService, dict[str, object]]:
    dependencies = {
        "tasks": MemoryTasks(task),
        "planning_documents": PlanningDocumentsFake(),
        "documents": DocumentsFake(),
        "validation": ValidationFake(validation_gates),
        "conformance": ConformanceFake(),
        "commands": CommandsFake(command_status),
        "evidence": EvidenceFake(),
        "events": EventsFake(),
        "clock": FixedClock(),
    }
    return VerificationService(**dependencies), dependencies


def _task(*, plan_status: str = "approved") -> dict:
    return {
        "id": "TF-1",
        "type": "feature",
        "slug": "verification",
        "status": "open",
        "stage": "audit",
        "workflow_phase": "execution",
        "plan_status": plan_status,
        "plan_review_round": 0,
        "max_plan_review_rounds": 3,
        "spec_status": "frozen",
        "verify_status": "not_run",
        "audit_attempts": 0,
        "max_audit_attempts": 10,
        "gates": [],
        "docs": {"brief": "BRIEF.md", "plan": "PLAN.md", "verify": "VERIFY.md"},
        "verify_commands": ["python -m unittest"],
        "test_strategy": {
            "normal_cases": [{"name": "happy"}],
            "edge_cases": [{"name": "empty"}],
            "exception_cases": [{"name": "failure"}],
            "verification_methods": [{"target": "happy", "method": "unit"}],
            "external_llm": {"required": False, "status": "not_needed"},
        },
        "subtasks": [],
        "meta": {},
    }


if __name__ == "__main__":
    unittest.main()
