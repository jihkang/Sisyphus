from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.conformance import append_conformance_log
from sisyphus.episode_trace import append_episode_step, build_episode_step, next_episode_step
from sisyphus.eval.loop import TEST_FIRST_LOOP_PHASES, build_task_eval_loop_result
from sisyphus.evidence_graph import write_evidence_graph
from sisyphus.reward import REWARD_METRIC_NAMES


class EvalLoopTests(unittest.TestCase):
    def test_scores_closed_verified_task_with_evidence_and_episode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            task = _task(status="closed", verify_status="passed")
            write_evidence_graph(task_dir, _complete_evidence_graph(task["id"]))
            _append_action(task_dir, task["id"], "sisyphus.verify_task", ok=True)

            result = build_task_eval_loop_result(task, task_dir)
            payload = result.to_dict()

            self.assertEqual(result.terminal_status, "closed_verified")
            self.assertEqual(result.action_count, 1)
            self.assertGreater(result.reward.total, 3.0)
            self.assertEqual(set(REWARD_METRIC_NAMES), set(result.metrics))
            self.assertEqual(payload["loop"]["shape"][0], "observation_t")
            self.assertEqual(payload["loop"]["test_first"]["status"], "todo")
            self.assertEqual(tuple(payload["loop"]["test_first"]["phases"]), TEST_FIRST_LOOP_PHASES)

    def test_false_close_gets_explicit_penalty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            task = _task(status="closed", verify_status="failed")

            result = build_task_eval_loop_result(task, task_dir)

            self.assertEqual(result.terminal_status, "false_closed")
            self.assertTrue(result.reward.facts.false_close)
            self.assertIn("false_close", result.reward.penalties)
            self.assertEqual(result.metrics["verify_passed"], 0.0)

    def test_conformance_yellow_and_red_are_visible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            yellow_task = _task(status="closed", verify_status="passed")
            append_conformance_log(
                yellow_task,
                checkpoint_type="post_exec",
                status="yellow",
                summary="unresolved drift",
                source="test",
                resolved=False,
                drift=1,
            )

            yellow = build_task_eval_loop_result(yellow_task, task_dir)

            self.assertEqual(yellow.reward.facts.conformance_status, "yellow")
            self.assertIn("conformance_not_green_at_close", yellow.reward.penalties)

            red_task = _task(status="open", verify_status="passed")
            append_conformance_log(
                red_task,
                checkpoint_type="post_exec",
                status="red",
                summary="blocking drift",
                source="test",
                resolved=False,
                drift=1,
            )

            red = build_task_eval_loop_result(red_task, task_dir)

            self.assertEqual(red.terminal_status, "conformance_drift")
            self.assertIn("conformance_red", red.reward.penalties)

    def test_missing_evidence_and_excessive_actions_are_penalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            task = _task(status="open", verify_status="passed")
            for index in range(3):
                _append_action(task_dir, task["id"], f"sisyphus.search.{index}", ok=True)

            result = build_task_eval_loop_result(task, task_dir, max_action_count=2)

            self.assertEqual(result.action_count, 3)
            self.assertEqual(result.reward.facts.evidence_status, "missing")
            self.assertTrue(result.reward.facts.excessive_action_count)
            self.assertIn("missing_evidence", result.reward.penalties)
            self.assertIn("excessive_action_count", result.reward.penalties)

    def test_missing_episode_files_are_tolerated_as_zero_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            task = _task(status="open", verify_status="not_run")

            result = build_task_eval_loop_result(task, task_dir)

            self.assertEqual(result.step_count, 0)
            self.assertEqual(result.action_count, 0)
            self.assertFalse(result.reward.facts.excessive_action_count)


def _append_action(task_dir: Path, task_id: str, action_name: str, *, ok: bool) -> None:
    episode_id = "ep-eval"
    step = build_episode_step(
        episode_id=episode_id,
        task_id=task_id,
        step=next_episode_step(task_dir, episode_id),
        observation={"task_id": task_id, "observation_hash": "sha256:before"},
        action_name=action_name,
        arguments={"task_id": task_id},
        result={"ok": ok},
        state_before={"verify_status": "not_run"},
        state_after={"verify_status": "passed" if ok else "failed"},
        actor={"agent_id": "eval-test"},
        timestamp="2026-06-14T00:00:00Z",
    )
    append_episode_step(task_dir, step)


def _complete_evidence_graph(task_id: str) -> dict[str, object]:
    return {
        "schema_version": "sisyphus.evidence_graph.v1",
        "task_id": task_id,
        "generated_at": "2026-06-14T00:00:00Z",
        "curated_evidence": [
            {
                "id": "ev-001",
                "type": "command_output",
                "claim": "Verification passed.",
                "source": {"command": "python -m unittest"},
                "verdict": "supports",
                "importance": "high",
                "blocking": False,
            }
        ],
        "unsupported_claims": [],
        "blocking_gaps": [],
    }


def _task(*, status: str, verify_status: str) -> dict:
    return {
        "id": "TF-eval",
        "type": "feature",
        "status": status,
        "stage": "exec",
        "workflow_phase": "worker_execution",
        "plan_status": "approved",
        "spec_status": "frozen",
        "verify_status": verify_status,
        "promotion": {"required": False, "status": "not_required"},
        "gates": [],
        "subtasks": [],
        "conformance": {"status": "green", "history": []},
        "design": {"mode": "none", "assessment": {}},
        "docs": {},
        "meta": {"evidence_graph_required": True},
    }


if __name__ == "__main__":
    unittest.main()
