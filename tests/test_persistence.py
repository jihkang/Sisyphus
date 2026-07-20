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
        from sisyphus.infra.persistence.task_repository import (
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
        from sisyphus.infra.persistence.task_repository import (
            load_task_record,
            save_task_record,
            update_task_record,
        )

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
        from sisyphus.infra.persistence.task_repository import save_task_record

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

    def test_promotion_state_save_does_not_dirty_the_task_worktree(self) -> None:
        from sisyphus.infra.config.loader import load_config
        from sisyphus.infra.persistence.task_records import FileTaskRecordAdapter
        from sisyphus.infra.persistence.task_repository import save_task_record

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            worktree_root = Path(tempdir) / "worktree"
            task_file = repo_root / ".planning" / "tasks" / "TF-1" / "task.json"
            task_file.parent.mkdir(parents=True)
            worktree_root.mkdir(parents=True)
            task = _task_record(repo_root, "TF-1")
            task["worktree_path"] = str(worktree_root)
            save_task_record(task_file, task)
            mirrored_task = worktree_root / ".planning" / "tasks" / "TF-1" / "task.json"
            original_mirror = mirrored_task.read_bytes()

            adapter = FileTaskRecordAdapter(repo_root, load_config(repo_root))
            loaded = adapter.load("TF-1")
            loaded["promotion"]["required"] = True
            loaded["promotion"]["status"] = "pushed"
            adapter.save_promotion_state(loaded)

            self.assertEqual(mirrored_task.read_bytes(), original_mirror)
            self.assertEqual(adapter.load("TF-1")["promotion"]["status"], "pushed")

    def test_task_support_sync_rejects_document_path_traversal(self) -> None:
        from sisyphus.infra.persistence.task_repository import sync_task_support_files
        from sisyphus.shared.paths import PathBoundaryError

        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            repo_root = root / "repo"
            worktree_root = root / "worktree"
            task_dir = repo_root / ".planning" / "tasks" / "TF-1"
            task_dir.mkdir(parents=True)
            worktree_root.mkdir()
            (task_dir / "task.json").write_text("{}\n", encoding="utf-8")
            task = _task_record(repo_root, "TF-1")
            task["worktree_path"] = str(worktree_root)
            task["docs"] = {"plan": "../../../../outside.txt"}

            with self.assertRaises(PathBoundaryError):
                sync_task_support_files(task)

            self.assertFalse((root / "outside.txt").exists())

    def test_task_support_sync_rejects_target_directory_symlink(self) -> None:
        from sisyphus.infra.persistence.task_repository import sync_task_support_files
        from sisyphus.infra.workspace.errors import WorkspaceFileSafetyError

        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            repo_root = root / "repo"
            worktree_root = root / "worktree"
            outside = root / "outside"
            task_dir = repo_root / ".planning" / "tasks" / "TF-1"
            task_dir.mkdir(parents=True)
            worktree_root.mkdir()
            outside.mkdir()
            (task_dir / "task.json").write_text("{}\n", encoding="utf-8")
            (worktree_root / ".planning").symlink_to(outside, target_is_directory=True)
            task = _task_record(repo_root, "TF-1")
            task["worktree_path"] = str(worktree_root)

            with self.assertRaises(WorkspaceFileSafetyError):
                sync_task_support_files(task)

            self.assertFalse((outside / "tasks" / "TF-1" / "task.json").exists())

    def test_task_support_sync_rejects_source_file_symlink(self) -> None:
        from sisyphus.infra.persistence.task_repository import sync_task_support_files
        from sisyphus.infra.workspace.errors import WorkspaceFileSafetyError

        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            repo_root = root / "repo"
            worktree_root = root / "worktree"
            task_dir = repo_root / ".planning" / "tasks" / "TF-1"
            task_dir.mkdir(parents=True)
            worktree_root.mkdir()
            (task_dir / "task.json").write_text("{}\n", encoding="utf-8")
            secret = root / "secret.txt"
            secret.write_text("do not mirror\n", encoding="utf-8")
            (task_dir / "PLAN.md").symlink_to(secret)
            task = _task_record(repo_root, "TF-1")
            task["worktree_path"] = str(worktree_root)
            task["docs"] = {"plan": "PLAN.md"}

            with self.assertRaises(WorkspaceFileSafetyError):
                sync_task_support_files(task)

            mirrored_plan = worktree_root / ".planning" / "tasks" / "TF-1" / "PLAN.md"
            self.assertFalse(mirrored_plan.exists())

    def test_agent_save_rejects_stale_loaded_record(self) -> None:
        from sisyphus.infra.persistence.agent_repository import (
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
