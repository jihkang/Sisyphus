from __future__ import annotations

from dataclasses import replace
import json
import sys
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.bootstrap import build_application
from sisyphus.domain.agent.models import Agent
from sisyphus.domain.task.models import Task
from sisyphus.infra.persistence.repositories import JsonAgentRepository, JsonTaskRepository
from sisyphus.shared.paths import PathBoundaryError


class ApplicationCompositionTests(unittest.TestCase):
    def test_composition_root_returns_typed_task_and_agent_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            task_dir = repo_root / ".planning" / "tasks" / "TF-test"
            agent_dir = task_dir / "agents"
            agent_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                json.dumps(
                    {
                        "id": "TF-test",
                        "type": "feature",
                        "slug": "test",
                        "status": "open",
                        "future_schema": {"version": 2},
                    }
                ),
                encoding="utf-8",
            )
            (agent_dir / "worker-1.json").write_text(
                json.dumps(
                    {
                        "agent_id": "worker-1",
                        "parent_task_id": "TF-test",
                        "role": "worker",
                        "owned_paths": ["src"],
                        "command": [],
                    }
                ),
                encoding="utf-8",
            )
            application = build_application(repo_root, ".planning/tasks")

            task = application.tasks.get("TF-test")
            agent = application.agents.get("TF-test", "worker-1")

            self.assertIsInstance(task, Task)
            self.assertEqual(task.task_id, "TF-test")
            self.assertIsInstance(agent, Agent)
            self.assertEqual(agent.owned_paths, ("src",))

    def test_task_adapter_preserves_unknown_fields_when_saving_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            task_file = repo_root / ".planning" / "tasks" / "TF-test" / "task.json"
            task_file.parent.mkdir(parents=True)
            task_file.write_text(
                json.dumps(
                    {
                        "id": "TF-test",
                        "status": "open",
                        "future_schema": {"owner": "external"},
                    }
                ),
                encoding="utf-8",
            )
            repository = JsonTaskRepository(repo_root, ".planning/tasks")

            task = repository.get("TF-test")
            repository.save(replace(task, status="blocked"))
            persisted = json.loads(task_file.read_text(encoding="utf-8"))

            self.assertEqual(persisted["status"], "blocked")
            self.assertEqual(persisted["future_schema"], {"owner": "external"})

    def test_agent_adapter_can_create_and_read_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            repository = JsonAgentRepository(repo_root, ".planning/tasks")
            agent = Agent(
                agent_id="worker-1",
                parent_task_id="TF-test",
                role="worker",
                owned_paths=("src/sisyphus",),
                command=("python", "-m", "worker"),
            )

            repository.save(agent)
            restored = repository.get("TF-test", "worker-1")

            self.assertEqual(restored, agent)

    def test_agent_adapter_preserves_unknown_fields_when_saving_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            agent_file = (
                repo_root / ".planning" / "tasks" / "TF-test" / "agents" / "worker-1.json"
            )
            agent_file.parent.mkdir(parents=True)
            agent_file.write_text(
                json.dumps(
                    {
                        "agent_id": "worker-1",
                        "parent_task_id": "TF-test",
                        "role": "worker",
                        "status": "running",
                        "future_schema": {"owner": "external"},
                    }
                ),
                encoding="utf-8",
            )
            repository = JsonAgentRepository(repo_root, ".planning/tasks")

            agent = repository.get("TF-test", "worker-1")
            repository.save(replace(agent, status="completed"))
            persisted = json.loads(agent_file.read_text(encoding="utf-8"))

            self.assertEqual(persisted["status"], "completed")
            self.assertEqual(persisted["future_schema"], {"owner": "external"})

    def test_repository_paths_reject_task_and_agent_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            task_repository = JsonTaskRepository(repo_root, ".planning/tasks")
            agent_repository = JsonAgentRepository(repo_root, ".planning/tasks")

            with self.assertRaises(PathBoundaryError):
                task_repository.get("../../outside")
            with self.assertRaises(PathBoundaryError):
                agent_repository.get("../../outside", "worker")
            with self.assertRaises(PathBoundaryError):
                agent_repository.get("TF-test", "../../../outside")


if __name__ == "__main__":
    unittest.main()
