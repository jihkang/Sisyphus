from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.test_first import (
    TEST_FIRST_LOOP_PHASES,
    TEST_FIRST_STATUS_INCOMPLETE,
    TEST_FIRST_STATUS_NOT_RECORDED,
    TEST_FIRST_STATUS_SATISFIED,
    TEST_FIRST_STATUS_VIOLATED,
    evaluate_test_first_loop,
)


class TestFirstLoopTests(unittest.TestCase):
    def test_satisfied_when_required_phases_are_recorded_in_order(self) -> None:
        evaluation = evaluate_test_first_loop([_step(index, phase) for index, phase in enumerate(TEST_FIRST_LOOP_PHASES, start=1)])

        self.assertEqual(evaluation.status, TEST_FIRST_STATUS_SATISFIED)
        self.assertEqual(evaluation.missing_phases, ())
        self.assertEqual(evaluation.violations, ())

    def test_not_recorded_when_episode_has_no_phase_annotations(self) -> None:
        evaluation = evaluate_test_first_loop(
            [
                {
                    "step": 1,
                    "action": {"name": "sisyphus.verify_task", "arguments": {"task_id": "TF-test"}},
                    "result": {"ok": True},
                }
            ]
        )

        self.assertEqual(evaluation.status, TEST_FIRST_STATUS_NOT_RECORDED)
        self.assertEqual(evaluation.missing_phases, TEST_FIRST_LOOP_PHASES)

    def test_incomplete_when_only_some_phases_are_recorded(self) -> None:
        evaluation = evaluate_test_first_loop(
            [
                _step(1, "select_or_generate_tests"),
                _step(2, "run_baseline_tests"),
            ]
        )

        self.assertEqual(evaluation.status, TEST_FIRST_STATUS_INCOMPLETE)
        self.assertIn("implement_change", evaluation.missing_phases)

    def test_violated_when_implementation_precedes_baseline_tests(self) -> None:
        evaluation = evaluate_test_first_loop(
            [
                _step(1, "select_or_generate_tests"),
                _step(2, "implement_change"),
                _step(3, "run_baseline_tests"),
                _step(4, "rerun_tests"),
                _step(5, "record_evidence"),
            ]
        )

        self.assertEqual(evaluation.status, TEST_FIRST_STATUS_VIOLATED)
        self.assertTrue(evaluation.violations)

    def test_reads_phase_from_action_arguments_or_result(self) -> None:
        evaluation = evaluate_test_first_loop(
            [
                {"step": 1, "action": {"name": "select", "arguments": {"test_first_phase": "select_or_generate_tests"}}},
                {"step": 2, "result": {"test_first_phase": "run_baseline_tests"}},
                {"step": 3, "result": {"test_first": {"phase": "implement_change"}}},
                _step(4, "rerun_tests"),
                _step(5, "record_evidence"),
            ]
        )

        self.assertEqual(evaluation.status, TEST_FIRST_STATUS_SATISFIED)
        self.assertEqual([event.source for event in evaluation.observed_phases[:3]], [
            "action.arguments.test_first_phase",
            "result.test_first_phase",
            "result.test_first.phase",
        ])

    def test_unknown_phase_is_violation(self) -> None:
        evaluation = evaluate_test_first_loop([_step(1, "write_some_code")])

        self.assertEqual(evaluation.status, TEST_FIRST_STATUS_VIOLATED)
        self.assertIn("unknown test-first phase", evaluation.violations[0])


def _step(step: int, phase: str) -> dict[str, object]:
    return {
        "step": step,
        "action": {
            "name": f"phase.{phase}",
            "arguments": {},
            "test_first_phase": phase,
        },
        "result": {"ok": True},
    }


if __name__ == "__main__":
    unittest.main()
