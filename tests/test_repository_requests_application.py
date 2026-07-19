from __future__ import annotations

from pathlib import Path
import unittest

from sisyphus.application.commands.inbox import (
    QueueConversationCommand,
    QueuePullRequestMergedCommand,
)
from sisyphus.application.use_cases.repository_requests import (
    RepositoryRequestService,
    TaskRecordQueryService,
)


class FakeQueue:
    def __init__(self) -> None:
        self.conversation_commands: list[QueueConversationCommand] = []
        self.merge_commands: list[QueuePullRequestMergedCommand] = []

    def queue_conversation(
        self,
        command: QueueConversationCommand,
    ) -> tuple[dict[str, object], Path]:
        self.conversation_commands.append(command)
        return {"id": "evt-conversation", "payload": {}}, Path("/pending/conversation.json")

    def queue_pull_request_merged(
        self,
        command: QueuePullRequestMergedCommand,
    ) -> tuple[dict[str, object], Path]:
        self.merge_commands.append(command)
        return {"id": "evt-merge", "payload": {}}, Path("/pending/merge.json")


class FakeProcessing:
    def __init__(self, event: dict[str, object]) -> None:
        self.event = event
        self.paths: list[Path] = []

    def process(self, event_path: Path, *, stats=None) -> dict[str, object]:
        self.paths.append(event_path)
        return self.event


class FakeTasks:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self.records = records
        self.loaded: list[str] = []

    def load(self, task_id: str) -> dict[str, object]:
        self.loaded.append(task_id)
        return next(record for record in self.records if record["id"] == task_id)

    def list(self) -> tuple[dict[str, object], ...]:
        return tuple(self.records)

    def save(self, task: dict[str, object]) -> None:
        raise AssertionError("save is not part of repository request orchestration")

    def update(self, task_id, mutator):
        raise AssertionError("update is not part of repository request orchestration")


class RepositoryRequestServiceTests(unittest.TestCase):
    def _service(
        self,
        processed_event: dict[str, object],
        *,
        cycle_results: list[int] | None = None,
    ) -> tuple[RepositoryRequestService, FakeQueue, FakeProcessing, FakeTasks, list[int]]:
        queue = FakeQueue()
        processing = FakeProcessing(processed_event)
        tasks = FakeTasks([{"id": "TF-1", "status": "open"}])
        remaining = list(cycle_results or [])
        cycle_calls: list[int] = []

        def workflow_cycle() -> int:
            cycle_calls.append(1)
            return remaining.pop(0) if remaining else 0

        service = RepositoryRequestService(
            queue=queue,
            processing=processing,
            tasks=tasks,
            workflow_cycle=workflow_cycle,
            resolve_event_path=lambda event_id, status: Path(f"/{status}/{event_id}.json"),
        )
        return service, queue, processing, tasks, cycle_calls

    def test_request_processes_event_and_runs_workflow_until_stable(self) -> None:
        service, queue, processing, tasks, cycle_calls = self._service(
            {
                "status": "processed",
                "result": {"task_id": "TF-1"},
                "error": None,
            },
            cycle_results=[2, 1, 0],
        )

        result = service.request_task(
            QueueConversationCommand(message="create task", auto_run=True)
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.task_id, "TF-1")
        self.assertEqual(result.task, {"id": "TF-1", "status": "open"})
        self.assertEqual(result.orchestrated, 3)
        self.assertEqual(result.event_path, Path("/processed/evt-conversation.json"))
        self.assertEqual(len(cycle_calls), 3)
        self.assertEqual(tasks.loaded, ["TF-1"])
        self.assertEqual(processing.paths, [Path("/pending/conversation.json")])
        self.assertEqual(queue.conversation_commands[0].message, "create task")

    def test_request_does_not_run_workflow_when_auto_run_is_disabled(self) -> None:
        service, _, _, _, cycle_calls = self._service(
            {"status": "processed", "result": {"task_id": "TF-1"}, "error": None},
            cycle_results=[1, 0],
        )

        result = service.request_task(
            QueueConversationCommand(message="create only", auto_run=False)
        )

        self.assertEqual(result.orchestrated, 0)
        self.assertEqual(cycle_calls, [])

    def test_failed_request_preserves_error_without_loading_a_task(self) -> None:
        service, _, _, tasks, cycle_calls = self._service(
            {"status": "failed", "result": None, "error": "invalid request"},
            cycle_results=[1],
        )

        result = service.request_task(QueueConversationCommand(message="bad"))

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "invalid request")
        self.assertIsNone(result.task_id)
        self.assertIsNone(result.task)
        self.assertEqual(result.event_path, Path("/failed/evt-conversation.json"))
        self.assertEqual(tasks.loaded, [])
        self.assertEqual(cycle_calls, [])

    def test_merge_request_projects_receipt_and_closeout_fields(self) -> None:
        service, queue, _, _, _ = self._service(
            {
                "status": "processed",
                "result": {
                    "task_id": "TF-1",
                    "pr_number": 17,
                    "receipt_path": "/repo/receipt.json",
                    "changeset_path": "/repo/CHANGESET.md",
                    "close_attempted": True,
                    "closed": False,
                    "close_status": "blocked",
                    "close_gate_codes": ["VERIFY_REQUIRED"],
                    "child_retargeted_task_ids": ["TF-2"],
                },
                "error": None,
            }
        )

        result = service.record_merged_pull_request(
            QueuePullRequestMergedCommand(pr_number=17, title="Merged")
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.task_id, "TF-1")
        self.assertEqual(result.pr_number, 17)
        self.assertEqual(result.receipt_path, Path("/repo/receipt.json"))
        self.assertEqual(result.changeset_path, Path("/repo/CHANGESET.md"))
        self.assertTrue(result.close_attempted)
        self.assertFalse(result.closed)
        self.assertEqual(result.close_status, "blocked")
        self.assertEqual(result.close_gate_codes, ["VERIFY_REQUIRED"])
        self.assertEqual(result.child_retargeted_task_ids, ["TF-2"])
        self.assertEqual(queue.merge_commands[0].pr_number, 17)

    def test_task_record_query_returns_existing_wire_shapes(self) -> None:
        records = [{"id": "TF-1"}, {"id": "TF-2"}]
        service = TaskRecordQueryService(FakeTasks(records))

        self.assertEqual(service.get("TF-2"), {"id": "TF-2"})
        self.assertEqual(service.list(), records)


if __name__ == "__main__":
    unittest.main()
