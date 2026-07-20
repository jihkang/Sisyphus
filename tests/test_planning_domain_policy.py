from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.domain.planning import (
    PlanReviewState,
    PlanStatus,
    SpecState,
    SpecStatus,
    collect_plan_gate_specs,
    collect_spec_gate_specs,
    normalize_plan_status,
    normalize_spec_status,
)
from sisyphus.planning import collect_plan_gates, collect_spec_execution_gates


class PlanningDomainPolicyTests(unittest.TestCase):
    def test_plan_gate_matrix(self) -> None:
        cases = (
            (PlanReviewState(PlanStatus.APPROVED), ()),
            (PlanReviewState(PlanStatus.PENDING_REVIEW), ("PLAN_APPROVAL_REQUIRED",)),
            (PlanReviewState(PlanStatus.CHANGES_REQUESTED), ("PLAN_CHANGES_REQUESTED",)),
            (
                PlanReviewState(PlanStatus.CHANGES_REQUESTED, review_round=3, max_review_rounds=3),
                ("PLAN_REVIEW_LIMIT_REACHED",),
            ),
        )

        for state, expected_codes in cases:
            with self.subTest(state=state):
                gates = collect_plan_gate_specs(state, action="execution")
                self.assertEqual(tuple(gate.code for gate in gates), expected_codes)

    def test_spec_gate_matrix(self) -> None:
        self.assertEqual(collect_spec_gate_specs(SpecState(SpecStatus.FROZEN), action="verify"), ())
        self.assertEqual(
            tuple(
                gate.code
                for gate in collect_spec_gate_specs(SpecState(SpecStatus.DRAFT), action="verify")
            ),
            ("SPEC_FREEZE_REQUIRED",),
        )

    def test_legacy_status_normalization_is_explicit(self) -> None:
        self.assertEqual(normalize_plan_status(None), PlanStatus.APPROVED)
        self.assertEqual(normalize_plan_status("unknown"), PlanStatus.APPROVED)
        self.assertEqual(normalize_spec_status(None), SpecStatus.FROZEN)
        self.assertEqual(normalize_spec_status("unknown"), SpecStatus.FROZEN)

    def test_public_dict_adapter_matches_domain_policy(self) -> None:
        task = {
            "plan_status": "changes_requested",
            "plan_review_round": 1,
            "max_plan_review_rounds": 3,
            "spec_status": "draft",
        }

        plan_records = collect_plan_gates(task, action="execution")
        spec_records = collect_spec_execution_gates(task, action="execution")

        self.assertEqual([gate["code"] for gate in plan_records], ["PLAN_CHANGES_REQUESTED"])
        self.assertEqual([gate["code"] for gate in spec_records], ["SPEC_FREEZE_REQUIRED"])
        self.assertTrue(all(str(gate["created_at"]).endswith("Z") for gate in plan_records + spec_records))


if __name__ == "__main__":
    unittest.main()
