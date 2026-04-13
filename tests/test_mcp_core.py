from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from taskflow.config import load_config
from taskflow.conformance import append_conformance_log
from taskflow.events import new_event_envelope
from taskflow.mcp_core import SisyphusMcpCoreService
from taskflow.planning import approve_task_plan, freeze_task_spec
from taskflow.state import create_task_record, save_task_record
from taskflow.templates import materialize_task_templates


class McpCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text("", encoding="utf-8")
        self.config = load_config(self.repo_root)
        self.core = SisyphusMcpCoreService(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_task(self, slug: str = "mcp-core") -> dict:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug=slug,
        )
        materialize_task_templates(task)
        return task

    def test_lists_tools_and_resources(self) -> None:
        tool_names = {tool["name"] for tool in self.core.list_tools()}
        resource_uris = {resource["uri"] for resource in self.core.list_resources()}

        self.assertIn("sisyphus.request_task", tool_names)
        self.assertIn("task://<task-id>/conformance", resource_uris)
        request_tool = next(tool for tool in self.core.list_tools() if tool["name"] == "sisyphus.request_task")
        self.assertEqual(request_tool["inputSchema"]["required"], ["message"])
        self.assertFalse(request_tool["inputSchema"]["additionalProperties"])
        self.assertIn("task", next(tool for tool in self.core.list_tools() if tool["name"] == "sisyphus.get_task")["outputSchema"]["properties"])

    def test_reads_task_resources(self) -> None:
        task = self._new_task("record")

        record_payload = self.core.read_resource(f"task://{task['id']}/record")
        brief_payload = self.core.read_resource(f"task://{task['id']}/brief")

        self.assertEqual(record_payload["task"]["id"], task["id"])
        self.assertIn("# Brief", brief_payload)

    def test_reads_task_timeline_resource(self) -> None:
        task = self._new_task("timeline")
        task.setdefault("subtasks", []).append({"id": "S1", "title": "Wire MCP board", "category": "implementation"})
        append_conformance_log(
            task,
            checkpoint_type="spec_anchor",
            status="green",
            summary="spec anchored",
            source="tests",
            subtask_id="S1",
            resolved=True,
            drift=0,
        )
        append_conformance_log(
            task,
            checkpoint_type="post_exec",
            status="yellow",
            summary="verification mapping missing",
            source="tests",
            subtask_id="S1",
            resolved=False,
            drift=0,
        )
        save_task_record(self.repo_root / task["task_dir"] / "task.json", task)

        timeline_payload = self.core.read_resource(f"task://{task['id']}/timeline")

        self.assertEqual(timeline_payload["task_id"], task["id"])
        self.assertEqual(len(timeline_payload["task_history"]), 2)
        self.assertEqual(timeline_payload["subtasks"][0]["subtask_id"], "S1")
        self.assertEqual(len(timeline_payload["subtasks"][0]["history"]), 2)

    def test_reads_repo_status_and_schema_resources(self) -> None:
        task = self._new_task("board")

        conformance_payload = self.core.read_resource("repo://status/conformance")
        board_payload = self.core.read_resource("repo://status/board")
        schema_payload = self.core.read_resource("repo://schema/mcp")

        self.assertEqual(conformance_payload["tasks"][0]["task_id"], task["id"])
        self.assertEqual(board_payload["summary"]["task_count"], 1)
        self.assertIn("# Sisyphus MCP Schema", schema_payload)
        self.assertIn("required: message", schema_payload)
        self.assertIn("returns: ok, event_id, task_id, event_status, orchestrated, error", schema_payload)

    def test_reads_recent_event_resource(self) -> None:
        event_path = self.repo_root / ".planning" / "events.jsonl"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(
            "\n".join(
                [
                    new_event_envelope("task.created", data={"task_id": "TF-1"}, event_id="evt_1").to_json(),
                    new_event_envelope("task.updated", data={"task_id": "TF-1"}, event_id="evt_2").to_json(),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        payload = self.core.read_resource("repo://status/events")

        self.assertEqual(payload["events"][0]["event_id"], "evt_1")
        self.assertEqual(payload["events"][1]["event_id"], "evt_2")

    def test_calls_tool_against_repo_state(self) -> None:
        task = self._new_task("generate")
        approve_task_plan(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="reviewer",
            notes="approved",
        )
        freeze_task_spec(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="reviewer",
            notes="frozen",
        )

        payload = self.core.call_tool("sisyphus.subtasks_generate", {"task_id": task["id"]})

        self.assertEqual(payload["task_id"], task["id"])
        self.assertTrue(payload["subtasks"])
