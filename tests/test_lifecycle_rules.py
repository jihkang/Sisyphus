from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.conformance import append_conformance_log
from sisyphus.action_space import allowed_policy_actions, forbidden_policy_actions
from sisyphus.gates import dedupe_gates, make_gate
from sisyphus.lifecycle_rules import evaluate_transition
from sisyphus.lifecycle_state import LifecycleAction


class GateUtilityTests(unittest.TestCase):
    def test_dedupe_gates_ignores_created_at_but_preserves_subtask_scope(self) -> None:
        first = make_gate("VERIFY_REQUIRED", "task must pass verify before close", "close", created_at="t1")
        duplicate = make_gate("VERIFY_REQUIRED", "task must pass verify before close", "close", created_at="t2")
        subtask_scoped = make_gate(
            "VERIFY_REQUIRED",
            "task must pass verify before close",
            "close",
            subtask_id="subtask-001",
            created_at="t3",
        )

        deduped = dedupe_gates([first, duplicate, subtask_scoped])

        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["created_at"], "t1")
        self.assertEqual(deduped[1]["subtask_id"], "subtask-001")


class LifecycleRulesTests(unittest.TestCase):
    def test_spec_freeze_requires_plan_approval(self) -> None:
        task = _task(plan_status="pending_review", spec_status="draft")

        result = evaluate_transition(task, LifecycleAction.FREEZE_SPEC)

        self.assertFalse(result.allowed)
        self.assertEqual(result.blocking_codes, ("PLAN_APPROVAL_REQUIRED",))

    def test_execution_requires_plan_and_spec(self) -> None:
        task = _task(plan_status="approved", spec_status="draft")

        result = evaluate_transition(task, LifecycleAction.START_EXECUTION)

        self.assertFalse(result.allowed)
        self.assertEqual(result.blocking_codes, ("SPEC_FREEZE_REQUIRED",))

    def test_close_requires_verify_and_promotion_completion(self) -> None:
        task = _task(
            plan_status="approved",
            spec_status="frozen",
            verify_status="not_run",
            promotion={"required": True, "status": "promotion_pending"},
        )

        result = evaluate_transition(task, LifecycleAction.CLOSE)

        self.assertFalse(result.allowed)
        self.assertEqual(set(result.blocking_codes), {"VERIFY_REQUIRED", "PROMOTION_REQUIRED"})

    def test_close_allows_verified_non_promotable_green_task(self) -> None:
        task = _task(
            plan_status="approved",
            spec_status="frozen",
            verify_status="passed",
            promotion={"required": False, "status": "not_required"},
        )

        result = evaluate_transition(task, LifecycleAction.CLOSE)

        self.assertTrue(result.allowed)
        self.assertEqual(result.next_phase, "closed")

    def test_conformance_warning_blocks_close(self) -> None:
        task = _task(
            plan_status="approved",
            spec_status="frozen",
            verify_status="passed",
            promotion={"required": False, "status": "not_required"},
        )
        append_conformance_log(
            task,
            checkpoint_type="post_exec",
            status="yellow",
            summary="implementation drift requires review",
            source="test",
            resolved=False,
            drift=1,
        )

        result = evaluate_transition(task, LifecycleAction.CLOSE)

        self.assertFalse(result.allowed)
        self.assertEqual(result.blocking_codes, ("CONFORMANCE_WARNING_UNRESOLVED",))

    def test_policy_actions_exclude_human_gated_close_even_when_environment_allows_it(self) -> None:
        task = _task(
            plan_status="approved",
            spec_status="frozen",
            verify_status="passed",
            promotion={"required": False, "status": "not_required"},
        )

        allowed = set(allowed_policy_actions(task))
        forbidden = {item["action"]: item for item in forbidden_policy_actions(task)}

        self.assertIn("sisyphus.verify_task", allowed)
        self.assertNotIn("sisyphus.close_task", allowed)
        self.assertEqual(forbidden["sisyphus.close_task"]["risk"], "review_gated")
        self.assertTrue(forbidden["sisyphus.close_task"]["requires_human"])


def _task(
    *,
    plan_status: str = "pending_review",
    spec_status: str = "draft",
    verify_status: str = "not_run",
    promotion: dict | None = None,
) -> dict:
    return {
        "id": "TF-test",
        "type": "feature",
        "slug": "test",
        "status": "open",
        "stage": "spec",
        "workflow_phase": "plan_in_review",
        "plan_status": plan_status,
        "plan_review_round": 0,
        "max_plan_review_rounds": 3,
        "spec_status": spec_status,
        "verify_status": verify_status,
        "promotion": promotion or {"required": False, "status": "not_required"},
        "gates": [],
        "subtasks": [],
        "conformance": {"status": "green", "history": []},
        "design": {"mode": "none", "assessment": {}},
    }


if __name__ == "__main__":
    unittest.main()
