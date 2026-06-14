from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.conformance import append_conformance_log
from sisyphus.gates import make_gate
from sisyphus.reward import REWARD_METRIC_NAMES, reward_breakdown_metrics, score_task_outcome, task_outcome_facts


class RewardTests(unittest.TestCase):
    def test_scores_verified_green_closed_task(self) -> None:
        task = _task(status="closed", verify_status="passed")

        reward = score_task_outcome(task)

        self.assertGreater(reward.total, 3.0)
        self.assertEqual(reward.task_closed, 1.0)
        self.assertEqual(reward.verify_passed, 0.8)
        self.assertEqual(reward.conformance_green, 0.6)
        self.assertEqual(reward.penalties, {})

    def test_exposes_stable_metric_names(self) -> None:
        task = _task(status="closed", verify_status="passed")

        reward = score_task_outcome(task)
        metrics = reward_breakdown_metrics(reward)

        self.assertEqual(set(metrics), set(REWARD_METRIC_NAMES))
        self.assertEqual(metrics["reward_total"], reward.total)

    def test_penalizes_false_close_with_blocking_gates(self) -> None:
        task = _task(status="closed", verify_status="failed")
        task["gates"] = [make_gate("VERIFY_REQUIRED", "task must pass verify before close", "close")]

        reward = score_task_outcome(task)

        self.assertIn("false_close", reward.penalties)
        self.assertIn("blocking_gates_at_close", reward.penalties)
        self.assertLess(reward.total, 1.0)

    def test_penalizes_close_with_conformance_warning(self) -> None:
        task = _task(status="closed", verify_status="passed")
        append_conformance_log(
            task,
            checkpoint_type="post_exec",
            status="yellow",
            summary="drift requires review",
            source="test",
            resolved=False,
            drift=1,
        )

        facts = task_outcome_facts(task)
        reward = score_task_outcome(task)

        self.assertEqual(facts.conformance_status, "yellow")
        self.assertIn("conformance_not_green_at_close", reward.penalties)


def _task(*, status: str, verify_status: str) -> dict:
    return {
        "id": "TF-reward",
        "type": "feature",
        "status": status,
        "verify_status": verify_status,
        "promotion": {"required": False, "status": "not_required"},
        "gates": [],
        "subtasks": [],
        "conformance": {"status": "green", "history": []},
        "design": {"mode": "none", "assessment": {}},
    }


if __name__ == "__main__":
    unittest.main()
