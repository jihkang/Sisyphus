from __future__ import annotations

import json
import sys
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.config import load_config
from sisyphus.dataset_export import (
    DATASET_FORMAT_RL,
    DATASET_FORMAT_SFT,
    build_dataset_export,
    build_task_dataset_records,
    export_dataset,
)
from sisyphus.episode_trace import append_episode_step, build_episode_step, next_episode_step
from sisyphus.eval.loop import build_task_eval_loop_result
from sisyphus.evidence_graph import write_evidence_graph
from sisyphus.test_first import TEST_FIRST_LOOP_PHASES, TEST_FIRST_STATUS_SATISFIED


class DatasetExportTests(unittest.TestCase):
    def test_sft_records_use_observation_hash_and_action_payload_without_fabrication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            task = _task("TF-sft", task_dir, status="open", verify_status="failed")
            _append_action(task_dir, task["id"], "sisyphus.verify_task", ok=False)

            records = build_task_dataset_records(task, task_dir, format=DATASET_FORMAT_SFT)

            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(record["format"], "sft")
            self.assertFalse(record["result"]["ok"])
            self.assertEqual(record["terminal_status"], "verification_failed")
            messages = record["messages"]
            self.assertEqual([message["role"] for message in messages], ["system", "user", "assistant"])
            user_payload = json.loads(messages[1]["content"])
            assistant_payload = json.loads(messages[2]["content"])
            self.assertEqual(user_payload["observation_hash"], "sha256:before")
            self.assertEqual(user_payload["state_before"]["verify_status"], "not_run")
            self.assertEqual(assistant_payload["action"], "sisyphus.verify_task")
            self.assertEqual(assistant_payload["arguments"]["task_id"], "TF-sft")

    def test_rl_records_align_reward_metrics_and_test_first_with_eval_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            task = _task("TF-rl", task_dir, status="closed", verify_status="passed")
            write_evidence_graph(task_dir, _complete_evidence_graph(task["id"]))
            for phase in TEST_FIRST_LOOP_PHASES:
                _append_action(task_dir, task["id"], f"phase.{phase}", ok=True, test_first_phase=phase)

            records = build_task_dataset_records(task, task_dir, format=DATASET_FORMAT_RL)
            expected = build_task_eval_loop_result(task, task_dir, episode_id="ep-dataset").to_dict()

            self.assertEqual(len(records), len(TEST_FIRST_LOOP_PHASES))
            first = records[0]
            self.assertEqual(first["format"], "rl")
            self.assertEqual(first["reward"], expected["reward"])
            self.assertEqual(first["metrics"], expected["metrics"])
            self.assertEqual(first["terminal_status"], "closed_verified")
            self.assertEqual(first["test_first"]["status"], TEST_FIRST_STATUS_SATISFIED)
            self.assertEqual(first["transition"]["state_diff"]["verify_status"], ["not_run", "passed"])

    def test_repo_export_defaults_to_tasks_with_episode_records_and_supports_task_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / ".taskflow.toml").write_text("", encoding="utf-8")
            config = load_config(repo_root)
            task_a, task_a_dir = _write_repo_task(repo_root, "TF-a")
            task_b, task_b_dir = _write_repo_task(repo_root, "TF-b")
            _write_repo_task(repo_root, "TF-no-episodes")
            _append_action(task_a_dir, task_a["id"], "sisyphus.search", ok=True)
            _append_action(task_b_dir, task_b["id"], "sisyphus.verify_task", ok=False)

            all_result = build_dataset_export(repo_root, config, format=DATASET_FORMAT_RL)
            scoped_result = build_dataset_export(repo_root, config, format=DATASET_FORMAT_RL, task_id="TF-b")

            self.assertEqual(all_result.task_ids, ("TF-a", "TF-b"))
            self.assertEqual(all_result.record_count, 2)
            self.assertEqual(scoped_result.task_ids, ("TF-b",))
            self.assertEqual(scoped_result.record_count, 1)
            self.assertEqual(scoped_result.records[0]["task_id"], "TF-b")

    def test_export_dataset_writes_deterministic_jsonl_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / ".taskflow.toml").write_text("", encoding="utf-8")
            config = load_config(repo_root)
            task, task_dir = _write_repo_task(repo_root, "TF-output")
            _append_action(task_dir, task["id"], "sisyphus.context_build", ok=True)
            output_path = repo_root / "artifacts" / "dataset.jsonl"

            result = export_dataset(
                repo_root,
                config,
                format=DATASET_FORMAT_SFT,
                task_id="TF-output",
                output_path=output_path,
            )

            self.assertEqual(result.output_path, output_path)
            self.assertEqual(result.record_count, 1)
            lines = output_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0]), result.records[0])

    def test_unknown_export_format_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            task = _task("TF-bad-format", task_dir, status="open", verify_status="not_run")

            with self.assertRaisesRegex(ValueError, "unsupported dataset export format"):
                build_task_dataset_records(task, task_dir, format="bad")


def _append_action(
    task_dir: Path,
    task_id: str,
    action_name: str,
    *,
    ok: bool,
    test_first_phase: str | None = None,
) -> None:
    episode_id = "ep-dataset"
    step = build_episode_step(
        episode_id=episode_id,
        task_id=task_id,
        step=next_episode_step(task_dir, episode_id),
        observation={"task_id": task_id, "observation_hash": "sha256:before"},
        action_name=action_name,
        arguments={"task_id": task_id, **({"test_first_phase": test_first_phase} if test_first_phase else {})},
        result={"ok": ok},
        state_before={"verify_status": "not_run"},
        state_after={"verify_status": "passed" if ok else "failed"},
        actor={"agent_id": "dataset-test"},
        timestamp="2026-06-14T00:00:00Z",
    )
    append_episode_step(task_dir, step)


def _write_repo_task(repo_root: Path, task_id: str) -> tuple[dict[str, object], Path]:
    task_dir = repo_root / ".planning" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    task = _task(task_id, task_dir, status="open", verify_status="not_run")
    task["repo_root"] = str(repo_root)
    task["task_dir"] = f".planning/tasks/{task_id}"
    (task_dir / "task.json").write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    return task, task_dir


def _task(task_id: str, task_dir: Path, *, status: str, verify_status: str) -> dict[str, object]:
    return {
        "id": task_id,
        "type": "feature",
        "slug": task_id.lower(),
        "status": status,
        "stage": "done" if status == "closed" else "exec",
        "workflow_phase": "closed" if status == "closed" else "worker_execution",
        "plan_status": "approved",
        "spec_status": "frozen",
        "verify_status": verify_status,
        "promotion": {"required": False, "status": "not_required"},
        "gates": [],
        "subtasks": [],
        "conformance": {"status": "green", "history": []},
        "design": {"mode": "none", "assessment": {}},
        "docs": {},
        "task_dir": str(task_dir),
        "meta": {"evidence_graph_required": True},
    }


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


if __name__ == "__main__":
    unittest.main()
