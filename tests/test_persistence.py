from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import time
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


class PersistenceSafetyTests(unittest.TestCase):
    def test_task_save_rejects_stale_loaded_record(self) -> None:
        from sisyphus.domain.task.repository import (
            ConcurrentTaskUpdateError,
            load_task_record,
            save_task_record,
        )

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            task_file = repo_root / ".planning" / "tasks" / "TF-1" / "task.json"
            task_file.parent.mkdir(parents=True)
            save_task_record(task_file, _task_record(repo_root, "TF-1"), mirror_support=False)

            first, _ = load_task_record(repo_root, ".planning/tasks", "TF-1")
            second, _ = load_task_record(repo_root, ".planning/tasks", "TF-1")

            time.sleep(0.01)
            first["status"] = "blocked"
            save_task_record(task_file, first, mirror_support=False)

            second["status"] = "verified"
            with self.assertRaises(ConcurrentTaskUpdateError):
                save_task_record(task_file, second, mirror_support=False)

            reloaded, _ = load_task_record(repo_root, ".planning/tasks", "TF-1")
            self.assertEqual(reloaded["status"], "blocked")

    def test_update_task_record_mutates_current_record_under_lock(self) -> None:
        from sisyphus.domain.task.repository import load_task_record, save_task_record, update_task_record

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            task_file = repo_root / ".planning" / "tasks" / "TF-1" / "task.json"
            task_file.parent.mkdir(parents=True)
            save_task_record(task_file, _task_record(repo_root, "TF-1"), mirror_support=False)

            stale, _ = load_task_record(repo_root, ".planning/tasks", "TF-1")

            def mutate_current(task: dict) -> None:
                task["workflow_phase"] = "needs_user_input"

            updated, _ = update_task_record(
                repo_root,
                ".planning/tasks",
                "TF-1",
                mutate_current,
                mirror_support=False,
            )
            self.assertEqual(updated["workflow_phase"], "needs_user_input")

            stale["status"] = "verified"
            with self.assertRaises(RuntimeError):
                save_task_record(task_file, stale, mirror_support=False)

    def test_task_support_sync_can_be_disabled_explicitly(self) -> None:
        from sisyphus.domain.task.repository import save_task_record

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            worktree_root = Path(tempdir) / "worktree"
            task_file = repo_root / ".planning" / "tasks" / "TF-1" / "task.json"
            task_file.parent.mkdir(parents=True)
            worktree_root.mkdir(parents=True)
            task = _task_record(repo_root, "TF-1")
            task["worktree_path"] = str(worktree_root)

            save_task_record(task_file, task, mirror_support=False)
            mirrored_task = worktree_root / ".planning" / "tasks" / "TF-1" / "task.json"
            self.assertFalse(mirrored_task.exists())

            save_task_record(task_file, task)
            self.assertTrue(mirrored_task.exists())

    def test_agent_save_rejects_stale_loaded_record(self) -> None:
        from sisyphus.domain.agent.repository import (
            ConcurrentAgentUpdateError,
            read_agent_record,
            save_agent_record,
        )

        with tempfile.TemporaryDirectory() as tempdir:
            agent_file = Path(tempdir) / "agent.json"
            save_agent_record(agent_file, {"agent_id": "worker-1", "status": "running"})

            first = read_agent_record(agent_file)
            second = read_agent_record(agent_file)

            time.sleep(0.01)
            first["current_step"] = "one"
            save_agent_record(agent_file, first)

            second["current_step"] = "two"
            with self.assertRaises(ConcurrentAgentUpdateError):
                save_agent_record(agent_file, second)

            self.assertEqual(read_agent_record(agent_file)["current_step"], "one")


def _task_record(repo_root: Path, task_id: str) -> dict:
    return {
        "id": task_id,
        "type": "feature",
        "slug": "example",
        "status": "open",
        "stage": "spec",
        "repo_root": str(repo_root),
        "task_dir": f".planning/tasks/{task_id}",
        "worktree_path": "",
        "branch": "feat/example",
        "base_branch": "main",
    }


if __name__ == "__main__":
    unittest.main()
