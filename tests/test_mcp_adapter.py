from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.mcp_adapter import call_mcp_tool, list_mcp_resources, list_mcp_tools, read_mcp_resource
from sisyphus.planning import approve_task_plan, freeze_task_spec
from sisyphus.state import create_task_record
from sisyphus.templates import materialize_task_templates
from sisyphus.config import load_config


class McpAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text("", encoding="utf-8")
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_task(self, slug: str = "mcp-task") -> dict:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug=slug,
        )
        materialize_task_templates(task)
        return task

    def test_lists_tools_and_resources(self) -> None:
        tool_names = {tool["name"] for tool in list_mcp_tools()}
        resource_uris = {resource["uri"] for resource in list_mcp_resources()}

        self.assertIn("sisyphus.request_task", tool_names)
        self.assertIn("sisyphus.verify_task", tool_names)
        self.assertIn("repo://status/tasks", resource_uris)
        self.assertIn("task://<task-id>/conformance", resource_uris)

    def test_read_task_record_and_conformance_resources(self) -> None:
        task = self._new_task("record")

        record_payload = read_mcp_resource(self.repo_root, f"task://{task['id']}/record")
        conformance_payload = read_mcp_resource(self.repo_root, f"task://{task['id']}/conformance")

        self.assertEqual(record_payload["task"]["id"], task["id"])
        self.assertEqual(conformance_payload["conformance"]["status"], "green")

    def test_read_task_markdown_resource(self) -> None:
        task = self._new_task("brief")

        brief = read_mcp_resource(self.repo_root, f"task://{task['id']}/brief")

        self.assertIn("# Brief", brief)

    def test_call_get_task_and_list_tasks_tools(self) -> None:
        task = self._new_task("list")

        list_payload = call_mcp_tool(self.repo_root, "sisyphus.list_tasks")
        get_payload = call_mcp_tool(self.repo_root, "sisyphus.get_task", {"task_id": task["id"]})

        self.assertEqual(len(list_payload["tasks"]), 1)
        self.assertEqual(get_payload["task"]["id"], task["id"])

    def test_call_subtasks_generate_tool(self) -> None:
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

        payload = call_mcp_tool(self.repo_root, "sisyphus.subtasks_generate", {"task_id": task["id"]})

        self.assertEqual(payload["task_id"], task["id"])
        self.assertTrue(payload["subtasks"])


if __name__ == "__main__":
    unittest.main()
