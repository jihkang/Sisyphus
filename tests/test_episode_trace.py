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

from sisyphus.episode_trace import (
    append_episode_step,
    build_episode_step,
    check_episode_trace,
    default_episode_id,
    diff_task_state,
    next_episode_step,
    read_episode_steps,
)
from sisyphus.shared.paths import PathBoundaryError


class EpisodeTraceTests(unittest.TestCase):
    def test_diff_task_state_records_changed_top_level_fields(self) -> None:
        before = {"status": "open", "verify_status": "not_run", "unchanged": 1}
        after = {"status": "verified", "verify_status": "passed", "unchanged": 1}

        diff = diff_task_state(before, after)

        self.assertEqual(diff["status"], ["open", "verified"])
        self.assertEqual(diff["verify_status"], ["not_run", "passed"])
        self.assertNotIn("unchanged", diff)

    def test_append_episode_step_writes_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            step = build_episode_step(
                episode_id="ep-test",
                task_id="TF-test",
                step=1,
                observation={"task_id": "TF-test", "observation_hash": "sha256:abc"},
                action_name="sisyphus.verify_task",
                arguments={"task_id": "TF-test"},
                result={"ok": True},
                state_before={"verify_status": "not_run"},
                state_after={"verify_status": "passed"},
                actor={"agent_id": "worker-1"},
                timestamp="2026-06-14T00:00:00Z",
            )

            path = append_episode_step(task_dir, step)

            payload = json.loads(path.read_text(encoding="utf-8").strip())
            self.assertEqual(payload["episode_id"], "ep-test")
            self.assertEqual(payload["state_ref"], "task://TF-test/observation")
            self.assertEqual(payload["observation_hash"], "sha256:abc")
            self.assertEqual(payload["state_before"]["verify_status"], "not_run")
            self.assertEqual(payload["state_after"]["verify_status"], "passed")
            self.assertEqual(payload["state_diff"]["verify_status"], ["not_run", "passed"])

    def test_trace_check_summarizes_valid_episode_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            episode_id = default_episode_id("TF-test", actor_id="mcp")
            first = build_episode_step(
                episode_id=episode_id,
                task_id="TF-test",
                step=next_episode_step(task_dir, episode_id),
                observation={"task_id": "TF-test", "observation_hash": "sha256:abc"},
                action_name="sisyphus.verify_task",
                arguments={"task_id": "TF-test"},
                result={"status": "passed"},
                state_before={"verify_status": "not_run"},
                state_after={"verify_status": "passed"},
                actor={"agent_id": "mcp"},
                timestamp="2026-06-14T00:00:00Z",
            )
            append_episode_step(task_dir, first)

            summary = check_episode_trace(task_dir, task_id="TF-test", episode_id=episode_id)

            self.assertTrue(summary["ok"])
            self.assertEqual(summary["episode_count"], 1)
            self.assertEqual(summary["step_count"], 1)
            self.assertEqual(summary["actions"], ["sisyphus.verify_task"])

    def test_episode_id_and_directory_cannot_escape_task_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            task_dir = Path(tmp)
            with self.assertRaisesRegex(ValueError, "invalid episode id"):
                read_episode_steps(task_dir, episode_id="../escape")

            episode_dir = task_dir / "artifacts" / "episodes"
            episode_dir.parent.mkdir(parents=True)
            episode_dir.symlink_to(Path(outside), target_is_directory=True)
            step = build_episode_step(
                episode_id="ep-safe",
                task_id="TF-test",
                step=1,
                observation={"observation_hash": "sha256:abc"},
                action_name="sisyphus.verify_task",
                arguments={},
                result={},
                state_before={},
                state_after={},
                timestamp="2026-06-14T00:00:00Z",
            )

            with self.assertRaisesRegex(PathBoundaryError, "escapes root"):
                append_episode_step(task_dir, step)


if __name__ == "__main__":
    unittest.main()
