from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.domain.lifecycle import (
    ConformanceState,
    LifecycleAction,
    LifecycleSnapshot,
    PlanStatus,
    PromotionState,
    SpecStatus,
    SubtaskConformance,
    evaluate_lifecycle_policy,
)
from sisyphus.lifecycle_rules import evaluate_transition


class LifecycleDomainPolicyTests(unittest.TestCase):
    def test_policy_evaluates_all_actions_without_record_or_clock_dependencies(self) -> None:
        snapshot = _snapshot()
        expected = {
            LifecycleAction.APPROVE_PLAN: (True, "spec_drafting"),
            LifecycleAction.REQUEST_PLAN_CHANGES: (True, "plan_revision"),
            LifecycleAction.REVISE_PLAN: (False, None),
            LifecycleAction.FREEZE_SPEC: (True, "subtask_planning"),
            LifecycleAction.GENERATE_SUBTASKS: (True, "execution"),
            LifecycleAction.START_EXECUTION: (True, "execution"),
            LifecycleAction.VERIFY: (True, "verified"),
            LifecycleAction.CLOSE: (True, "closed"),
            LifecycleAction.EXECUTE_PROMOTION: (True, "promotion_pending"),
            LifecycleAction.RECORD_MERGED_PR: (True, "execution"),
        }

        actual = {
            action: (
                (decision := evaluate_lifecycle_policy(snapshot, action)).allowed,
                decision.next_phase,
            )
            for action in LifecycleAction
        }

        self.assertEqual(actual, expected)

    def test_policy_preserves_gate_order_and_subtask_scope(self) -> None:
        snapshot = _snapshot(
            verify_status="not_run",
            conformance=ConformanceState(
                status="red",
                unresolved_warning_count=1,
                last_checkpoint_type="post_exec",
                subtasks=(
                    SubtaskConformance(
                        subtask_id="subtask-001",
                        status="red",
                        unresolved_warning_count=1,
                        last_checkpoint_type="pre_verify",
                    ),
                ),
            ),
            promotion=PromotionState(required=True, status="promotion_pending"),
        )

        decision = evaluate_lifecycle_policy(snapshot, LifecycleAction.CLOSE)

        self.assertEqual(
            decision.blocking_codes,
            (
                "CONFORMANCE_BLOCKED",
                "CONFORMANCE_WARNING_UNRESOLVED",
                "CONFORMANCE_BLOCKED",
                "CONFORMANCE_WARNING_UNRESOLVED",
                "VERIFY_REQUIRED",
                "PROMOTION_REQUIRED",
            ),
        )
        self.assertEqual(decision.gates[2].subtask_id, "subtask-001")
        self.assertIn("\x60subtask-001\x60", decision.gates[2].message)

    def test_review_limit_takes_precedence_over_plan_status_gate(self) -> None:
        snapshot = _snapshot(
            plan_status=PlanStatus.CHANGES_REQUESTED,
            plan_review_round=3,
            max_plan_review_rounds=3,
        )

        decision = evaluate_lifecycle_policy(snapshot, LifecycleAction.VERIFY)

        self.assertEqual(decision.blocking_codes, ("PLAN_REVIEW_LIMIT_REACHED",))

    def test_recorded_promotion_is_complete(self) -> None:
        snapshot = _snapshot(promotion=PromotionState(required=True, status="promotion_recorded"))

        decision = evaluate_lifecycle_policy(snapshot, LifecycleAction.CLOSE)

        self.assertTrue(decision.allowed)


class LifecycleCompatibilityAdapterTests(unittest.TestCase):
    def test_public_facade_keeps_gate_record_shape(self) -> None:
        task = _task(plan_status="pending_review", spec_status="draft")

        result = evaluate_transition(task, LifecycleAction.START_EXECUTION)

        self.assertEqual(
            [gate["code"] for gate in result.gates],
            ["PLAN_APPROVAL_REQUIRED", "SPEC_FREEZE_REQUIRED"],
        )
        for gate in result.gates:
            self.assertEqual(set(gate), {"code", "message", "blocking", "source", "created_at"})
            self.assertTrue(str(gate["created_at"]).endswith("Z"))

    def test_legacy_missing_plan_and_spec_fields_keep_approved_frozen_defaults(self) -> None:
        task = _task()
        task.pop("plan_status")
        task.pop("spec_status")

        result = evaluate_transition(task, LifecycleAction.START_EXECUTION)

        self.assertTrue(result.allowed)
        self.assertEqual(result.next_phase, "execution")

    def test_non_conformance_action_does_not_add_record_defaults(self) -> None:
        task = _task()
        task.pop("conformance")
        task.pop("design")
        task.pop("promotion")
        before = deepcopy(task)

        result = evaluate_transition(task, LifecycleAction.APPROVE_PLAN)

        self.assertTrue(result.allowed)
        self.assertEqual(task, before)

    def test_closed_task_short_circuits_without_mutating_missing_defaults(self) -> None:
        task = _task()
        task["status"] = "closed"
        task.pop("conformance")
        task.pop("design")
        task.pop("promotion")
        before = deepcopy(task)

        result = evaluate_transition(task, LifecycleAction.START_EXECUTION)

        self.assertFalse(result.allowed)
        self.assertEqual(result.blocking_codes, ("TASK_CLOSED",))
        self.assertEqual(task, before)

    def test_conformance_action_preserves_legacy_default_materialization(self) -> None:
        task = _task()
        task.pop("conformance")
        task.pop("design")

        result = evaluate_transition(task, LifecycleAction.START_EXECUTION)

        self.assertTrue(result.allowed)
        self.assertIn("conformance", task)
        self.assertIn("design", task)

    def test_unknown_string_action_still_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_transition(_task(), "not-an-action")

    def test_subtask_gate_preserves_identifier_whitespace(self) -> None:
        task = _task()
        task["conformance"] = {"status": "green", "history": []}
        task["subtasks"] = [
            {
                "id": "  subtask-001  ",
                "conformance": {
                    "status": "red",
                    "unresolved_warning_count": 0,
                    "history": [],
                },
            }
        ]

        result = evaluate_transition(task, LifecycleAction.VERIFY)

        scoped_gate = next(gate for gate in result.gates if gate.get("subtask_id"))
        self.assertEqual(scoped_gate["subtask_id"], "  subtask-001  ")


def _snapshot(
    *,
    plan_status: PlanStatus = PlanStatus.APPROVED,
    plan_review_round: int = 0,
    max_plan_review_rounds: int = 3,
    verify_status: str = "passed",
    conformance: ConformanceState = ConformanceState(),
    promotion: PromotionState = PromotionState(required=False, status="not_required"),
) -> LifecycleSnapshot:
    return LifecycleSnapshot(
        current_phase="execution",
        closed=False,
        plan_status=plan_status,
        plan_review_round=plan_review_round,
        max_plan_review_rounds=max_plan_review_rounds,
        spec_status=SpecStatus.FROZEN,
        verify_status=verify_status,
        conformance=conformance,
        promotion=promotion,
    )


def _task(
    *,
    plan_status: str = "approved",
    spec_status: str = "frozen",
) -> dict:
    return {
        "id": "TF-test",
        "type": "feature",
        "slug": "test",
        "status": "open",
        "stage": "spec",
        "workflow_phase": "execution",
        "plan_status": plan_status,
        "plan_review_round": 0,
        "max_plan_review_rounds": 3,
        "spec_status": spec_status,
        "verify_status": "passed",
        "promotion": {"required": False, "status": "not_required"},
        "gates": [],
        "subtasks": [],
        "conformance": {"status": "green", "history": []},
        "design": {"mode": "none", "assessment": {}},
    }


if __name__ == "__main__":
    unittest.main()
