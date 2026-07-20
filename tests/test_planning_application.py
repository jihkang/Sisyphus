from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from sisyphus.application.use_cases.planning import PlanningService  # noqa: E402
from sisyphus.application.results.planning import SpecValidationOutcome  # noqa: E402
from sisyphus.infra.orchestration.planning_adapters import DesignConformanceAdapter  # noqa: E402


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


class DocumentsFake:
    def __init__(self, strategy: dict | None = None) -> None:
        self.strategy = strategy
        self.calls: list[str] = []

    def sync_strategy(self, task_id: str, task: dict) -> dict:
        self.calls.append(task_id)
        if self.strategy is not None:
            task["test_strategy"] = deepcopy(self.strategy)
        return task


class ValidationFake:
    def __init__(self, gates_by_action: dict[str, tuple[dict, ...]] | None = None) -> None:
        self.gates_by_action = gates_by_action or {}
        self.calls: list[tuple[str, bool, bool]] = []
        self.validate_calls: list[tuple[str, bool]] = []

    def validate(self, task_id: str, *, persist: bool = True) -> SpecValidationOutcome:
        self.validate_calls.append((task_id, persist))
        return SpecValidationOutcome(
            task_id=task_id,
            status="passed",
            stale=False,
            report={"status": "passed"},
            report_path=Path("/task/artifacts/spec-validation/latest.json"),
            gates=[],
        )

    def collect_gates(
        self,
        task_id: str,
        task: dict,
        *,
        action: str,
        refresh: bool = False,
        require_existing_report: bool = False,
    ) -> tuple[dict, ...]:
        self.calls.append((action, refresh, require_existing_report))
        return self.gates_by_action.get(action, ())


class DesignConformanceFake:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def mark_design_anchor(self, task: dict, *, source: str) -> dict:
        self.calls.append(source)
        task.setdefault("conformance", {})["last_design_anchor_source"] = source
        return task


class InterventionsFake:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def required(self, **request: str) -> None:
        self.calls.append(request)


class FixedClock:
    def now(self) -> str:
        return "2026-07-19T12:00:00Z"


class PlanningApplicationTests(unittest.TestCase):
    def test_validate_spec_delegates_persistence_choice_to_validation_port(self) -> None:
        service, dependencies = _service(_task())

        outcome = service.validate_spec("TF-1", persist=False)

        self.assertEqual(outcome.status, "passed")
        self.assertEqual(dependencies["validation"].validate_calls, [("TF-1", False)])

    def test_approve_plan_synchronizes_documents_and_requests_spec_freeze(self) -> None:
        service, dependencies = _service(_task())

        outcome = service.approve_plan("TF-1", reviewer="reviewer", notes="approved")

        task = dependencies["tasks"].task
        self.assertEqual(outcome.plan_status, "approved")
        self.assertEqual(outcome.task_status, "open")
        self.assertEqual(task["workflow_phase"], "spec_drafting")
        self.assertEqual(task["plan_reviewed_at"], "2026-07-19T12:00:00Z")
        self.assertEqual(task["plan_review_history"][0]["action"], "approve")
        self.assertEqual(dependencies["documents"].calls, ["TF-1"])
        self.assertEqual(dependencies["validation"].calls, [("plan approval", True, False)])
        self.assertEqual(dependencies["interventions"].calls[0]["reason"], "spec_freeze_required")

    def test_validation_gate_blocks_plan_approval_without_status_drift(self) -> None:
        gate = {
            "code": "SPEC_VALIDATION_FAILED",
            "message": "invalid plan",
            "blocking": True,
            "source": "spec_validation",
            "created_at": "2026-07-19T12:00:00Z",
        }
        service, dependencies = _service(
            _task(),
            validation={"plan approval": (gate,)},
        )

        outcome = service.approve_plan("TF-1", reviewer="reviewer", notes=None)

        self.assertEqual(outcome.plan_status, "pending_review")
        self.assertEqual(outcome.task_status, "blocked")
        self.assertEqual(dependencies["tasks"].task["workflow_phase"], "plan_revision")
        self.assertEqual(outcome.gates, [gate])
        self.assertEqual(dependencies["interventions"].calls, [])

    def test_request_changes_then_revise_preserves_review_round(self) -> None:
        service, dependencies = _service(_task(plan_status="approved"))

        requested = service.request_changes("TF-1", reviewer="reviewer", notes="split work")
        revised = service.revise_plan("TF-1", author="author", notes="updated")

        self.assertEqual(requested.plan_status, "changes_requested")
        self.assertEqual(revised.plan_status, "pending_review")
        self.assertEqual(dependencies["tasks"].task["plan_review_round"], 1)
        self.assertEqual(
            [entry["action"] for entry in dependencies["tasks"].task["plan_review_history"]],
            ["request_changes", "revise"],
        )
        self.assertEqual(
            [call["reason"] for call in dependencies["interventions"].calls],
            ["plan_changes_requested", "plan_review_required"],
        )

    def test_freeze_spec_records_design_anchor_with_deterministic_time(self) -> None:
        service, dependencies = _service(
            _task(plan_status="approved", spec_status="draft"),
        )

        outcome = service.freeze_spec("TF-1", reviewer="reviewer", notes=None)

        task = dependencies["tasks"].task
        self.assertEqual(outcome.spec_status, "frozen")
        self.assertEqual(outcome.workflow_phase, "subtask_planning")
        self.assertEqual(task["spec_frozen_at"], "2026-07-19T12:00:00Z")
        self.assertEqual(task["design"]["frozen"]["frozen_at"], "2026-07-19T12:00:00Z")
        self.assertEqual(
            dependencies["design_conformance"].calls,
            ["planning.freeze_task_spec"],
        )

    def test_generate_subtasks_uses_synced_test_strategy(self) -> None:
        strategy = {
            "normal_cases": [{"name": "happy", "checked": True}],
            "edge_cases": [{"name": "empty", "checked": True}],
            "exception_cases": [],
        }
        service, dependencies = _service(
            _task(plan_status="approved", spec_status="frozen"),
            strategy=strategy,
        )

        outcome = service.generate_subtasks("TF-1")

        self.assertEqual(outcome.workflow_phase, "execution")
        self.assertEqual(
            [(item["id"], item["title"], item["category"]) for item in outcome.subtasks],
            [
                ("subtask-001", "happy", "normal"),
                ("subtask-002", "empty", "edge"),
            ],
        )
        self.assertEqual(
            dependencies["validation"].calls,
            [("subtask generation", False, True)],
        )


class PlanningAdapterTests(unittest.TestCase):
    def test_design_conformance_adapter_records_domain_anchor_with_injected_time(self) -> None:
        task = _task(plan_status="approved", spec_status="frozen")
        task["design"] = {
            "mode": "full",
            "layer_impact": "layer-adding",
            "required_artifacts": ["boundary_note"],
            "artifacts": {"boundary_note": "design/boundary.md"},
        }

        result = DesignConformanceAdapter(FixedClock()).mark_design_anchor(
            task,
            source="planning.freeze_task_spec",
        )

        conformance = result["conformance"]
        self.assertEqual(conformance["last_design_anchor_at"], "2026-07-19T12:00:00Z")
        self.assertEqual(conformance["last_design_anchor_source"], "planning.freeze_task_spec")
        self.assertEqual(conformance["last_checkpoint_type"], "design_anchor")
        self.assertEqual(conformance["status"], "green")
        self.assertEqual(len(conformance["history"]), 1)


def _service(
    task: dict,
    *,
    strategy: dict | None = None,
    validation: dict[str, tuple[dict, ...]] | None = None,
) -> tuple[PlanningService, dict[str, object]]:
    dependencies = {
        "tasks": MemoryTasks(task),
        "documents": DocumentsFake(strategy),
        "validation": ValidationFake(validation),
        "design_conformance": DesignConformanceFake(),
        "interventions": InterventionsFake(),
        "clock": FixedClock(),
    }
    return PlanningService(**dependencies), dependencies


def _task(
    *,
    plan_status: str = "pending_review",
    spec_status: str = "draft",
) -> dict:
    return {
        "id": "TF-1",
        "type": "feature",
        "slug": "clean-architecture",
        "status": "blocked",
        "stage": "plan_review",
        "workflow_phase": "plan_in_review",
        "plan_status": plan_status,
        "spec_status": spec_status,
        "verify_status": "not_run",
        "gates": [],
        "subtasks": [],
    }


if __name__ == "__main__":
    unittest.main()
