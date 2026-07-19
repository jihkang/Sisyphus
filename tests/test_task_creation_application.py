from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.application.commands.task import CreateTaskRecordCommand
from sisyphus.application.ports.task_creation import TaskWorkspaceProvisioningError
from sisyphus.application.use_cases.task_creation import (
    TaskCreationError,
    TaskRecordCreationService,
    TaskWorkspaceCreationService,
)
from sisyphus.config import load_config
import sisyphus.state as public_state


class FakeTaskFactory:
    def __init__(self) -> None:
        self.commands: list[CreateTaskRecordCommand] = []
        self.task = {"id": "TF-1", "type": "feature", "slug": "example"}

    def build(self, command: CreateTaskRecordCommand) -> dict[str, object]:
        self.commands.append(command)
        return self.task


class FakeTaskRecords:
    def __init__(self, existing: dict[str, object] | None = None) -> None:
        self.saved: list[dict[str, object]] = []
        self.existing = existing

    def save(self, task: dict[str, object]) -> None:
        self.saved.append(task)

    def load(self, task_id: str) -> dict[str, object]:
        if self.existing is None:
            raise FileNotFoundError(task_id)
        return self.existing


class FakeTaskWorkspace:
    def __init__(
        self,
        *,
        exists: bool = False,
        provisioning_error: str | None = None,
        rollback_errors: tuple[str, ...] = (),
    ) -> None:
        self.exists = exists
        self.provisioning_error = provisioning_error
        self.rollback_errors = rollback_errors
        self.calls: list[str] = []

    def task_directory_exists(self, task: dict[str, object]) -> bool:
        self.calls.append("exists")
        return self.exists

    def task_file(self, task: dict[str, object]) -> Path:
        self.calls.append("task_file")
        return Path("/repo/.planning/tasks/TF-1/task.json")

    def create_worktree(self, task: dict[str, object]) -> None:
        self.calls.append("create_worktree")
        if self.provisioning_error is not None:
            raise TaskWorkspaceProvisioningError(self.provisioning_error)

    def create_task_directory(self, task: dict[str, object]) -> None:
        self.calls.append("create_task_directory")

    def rollback(self, task: dict[str, object]) -> tuple[str, ...]:
        self.calls.append("rollback")
        return self.rollback_errors


class FakeTaskTemplates:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.materialized: list[dict[str, object]] = []

    def materialize(self, task: dict[str, object]) -> None:
        self.materialized.append(task)
        if self.error is not None:
            raise self.error


class TaskRecordCreationApplicationTests(unittest.TestCase):
    def test_service_builds_then_saves_the_same_task(self) -> None:
        factory = FakeTaskFactory()
        records = FakeTaskRecords()
        service = TaskRecordCreationService(factory=factory, tasks=records)
        command = CreateTaskRecordCommand(
            task_type="feature",
            slug="example",
            spec_validation_required=True,
        )

        result = service.create(command)

        self.assertIs(result, factory.task)
        self.assertEqual(factory.commands, [command])
        self.assertEqual(records.saved, [factory.task])

    def test_state_facade_delegates_record_creation_to_composition(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            config = load_config(repo_root)
            service = mock.Mock()
            service.create.return_value = {"id": "TF-created"}

            with mock.patch.object(
                public_state,
                "build_task_record_creation_service",
                return_value=service,
            ) as build_service:
                result = public_state.create_task_record(
                    repo_root,
                    config,
                    "issue",
                    "delegated",
                )

            self.assertEqual(result, {"id": "TF-created"})
            build_service.assert_called_once_with(repo_root, config)
            service.create.assert_called_once_with(
                CreateTaskRecordCommand(task_type="issue", slug="delegated")
            )


class TaskWorkspaceCreationApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = FakeTaskFactory()
        self.factory.task.update(
            {
                "branch": "feat/example",
                "base_branch": "main",
                "task_dir": ".planning/tasks/TF-1",
                "worktree_path": "/worktrees/TF-1",
                "status": "open",
            }
        )
        self.records = FakeTaskRecords()
        self.workspace = FakeTaskWorkspace()
        self.templates = FakeTaskTemplates()
        self.command = CreateTaskRecordCommand(task_type="feature", slug="example")

    def _service(self) -> TaskWorkspaceCreationService:
        return TaskWorkspaceCreationService(
            factory=self.factory,
            tasks=self.records,
            workspace=self.workspace,
            templates=self.templates,
        )

    def test_service_preserves_side_effect_order_and_result_identity(self) -> None:
        outcome = self._service().create(self.command)

        self.assertIs(outcome.task, self.factory.task)
        self.assertEqual(outcome.task_file, Path("/repo/.planning/tasks/TF-1/task.json"))
        self.assertEqual(self.records.saved, [self.factory.task])
        self.assertEqual(self.templates.materialized, [self.factory.task])
        self.assertEqual(
            self.workspace.calls,
            ["task_file", "exists", "create_worktree", "create_task_directory"],
        )

    def test_service_maps_workspace_provisioning_failure_without_rollback(self) -> None:
        self.workspace.provisioning_error = "branch already exists"

        with self.assertRaisesRegex(TaskCreationError, "branch already exists"):
            self._service().create(self.command)

        self.assertNotIn("rollback", self.workspace.calls)
        self.assertEqual(self.records.saved, [])

    def test_service_rolls_back_after_template_failure(self) -> None:
        self.templates.error = RuntimeError("template failed")

        with self.assertRaisesRegex(TaskCreationError, "task creation failed: template failed"):
            self._service().create(self.command)

        self.assertEqual(self.workspace.calls[-1], "rollback")

    def test_service_reports_incomplete_rollback(self) -> None:
        self.templates.error = RuntimeError("template failed")
        self.workspace.rollback_errors = ("worktree removal failed",)

        with self.assertRaisesRegex(
            TaskCreationError,
            "task creation failed and rollback was incomplete: worktree removal failed",
        ):
            self._service().create(self.command)

    def test_service_reports_closed_duplicate_with_followup_slug(self) -> None:
        self.workspace.exists = True
        self.records.existing = {
            **self.factory.task,
            "status": "closed",
            "slug": "example",
        }

        with self.assertRaisesRegex(TaskCreationError, "example-followup"):
            self._service().create(self.command)

        self.assertEqual(self.workspace.calls, ["task_file", "exists"])


if __name__ == "__main__":
    unittest.main()
