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
from sisyphus.application.use_cases.task_creation import TaskRecordCreationService
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
    def __init__(self) -> None:
        self.saved: list[dict[str, object]] = []

    def save(self, task: dict[str, object]) -> None:
        self.saved.append(task)


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


if __name__ == "__main__":
    unittest.main()
