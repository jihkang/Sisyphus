from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from sisyphus.application.conformance_records import ConformanceRecordService
from sisyphus.infra.documents.conformance_log import append_conformance_log_markdown


class FixedClock:
    def now(self) -> str:
        return "2026-07-19T12:00:00Z"


class ConformanceRecordTests(unittest.TestCase):
    def test_pre_and_post_execution_record_injected_time_and_ids(self) -> None:
        ids = iter(("task-1", "subtask-1", "task-2", "subtask-2", "task-3", "subtask-3"))
        service = ConformanceRecordService(FixedClock(), lambda: next(ids))
        task = _task()

        pre_status, _ = service.pre_execution(
            task,
            subtask_id="subtask-001",
            source="workflow.pre_exec",
        )
        post_status, _ = service.post_execution(
            task,
            subtask_id="subtask-001",
            exit_code=0,
            source="workflow.post_exec",
        )

        self.assertEqual((pre_status, post_status), ("green", "green"))
        self.assertEqual(
            [entry["id"] for entry in task["conformance"]["history"]],
            ["task-1", "task-2", "task-3"],
        )
        self.assertEqual(
            [entry["id"] for entry in task["subtasks"][0]["conformance"]["history"]],
            ["subtask-1", "subtask-2", "subtask-3"],
        )
        self.assertEqual(
            {entry["timestamp"] for entry in task["conformance"]["history"]},
            {"2026-07-19T12:00:00Z"},
        )

    def test_missing_subtask_records_only_task_failure(self) -> None:
        ids = iter(("task-anchor", "task-failure"))
        service = ConformanceRecordService(FixedClock(), lambda: next(ids))
        task = _task()

        status, summary = service.pre_execution(
            task,
            subtask_id="missing",
            source="workflow.pre_exec",
        )

        self.assertEqual(status, "red")
        self.assertIn("missing", summary)
        self.assertEqual(
            [entry["id"] for entry in task["conformance"]["history"]],
            ["task-anchor", "task-failure"],
        )
        self.assertEqual(task["subtasks"][0]["conformance"]["history"], [])

    def test_markdown_log_replaces_projection_without_duplication(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            task_dir = Path(temp_dir)
            log_path = task_dir / "LOG.md"
            log_path.write_text("# Log\n\nExisting entry.\n", encoding="utf-8")
            task = _task()
            task["docs"] = {"log": "LOG.md"}
            service = ConformanceRecordService(FixedClock(), iter(("task-1", "subtask-1")).__next__)
            service.mark_spec_anchor(
                task,
                source="workflow.pre_exec",
                subtask_id="subtask-001",
            )

            append_conformance_log_markdown(task, task_dir)
            first = log_path.read_text(encoding="utf-8")
            append_conformance_log_markdown(task, task_dir)

            self.assertEqual(log_path.read_text(encoding="utf-8"), first)
            self.assertEqual(first.count("## Conformance Checks"), 1)
            self.assertIn("subtask=subtask-001", first)


def _task() -> dict:
    title = "Implement behavior"
    return {
        "id": "TF-1",
        "type": "feature",
        "subtasks": [
            {
                "id": "subtask-001",
                "title": title,
                "category": "normal",
                "status": "queued",
            }
        ],
        "test_strategy": {
            "verification_methods": [{"target": title, "method": "unit test"}],
        },
    }


if __name__ == "__main__":
    unittest.main()
