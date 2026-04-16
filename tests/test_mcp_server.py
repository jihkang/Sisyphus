from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import mcp.types as types

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import sisyphus.mcp_server as legacy_sisyphus_mcp_server
from sisyphus.mcp_server import build_server, resolve_mcp_repo_root


class StubCoreService:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id

    def list_tools(self) -> list[dict[str, object]]:
        return [
            {
                "name": "sisyphus.get_task",
                "description": "stub",
                "inputSchema": {
                    "type": "object",
                    "properties": {"task_id": {"type": "string"}},
                    "required": ["task_id"],
                    "additionalProperties": False,
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {"task_id": {"type": "string"}},
                },
            }
        ]

    def list_resources(self) -> list[dict[str, object]]:
        return [
            {"uri": "repo://status/tasks", "description": "stub tasks"},
            {"uri": "task://<task-id>/brief", "description": "stub brief"},
        ]

    def call_tool(self, tool_name: str, arguments: dict[str, object] | None = None) -> dict[str, object]:
        return {"tool_name": tool_name, "task_id": self.task_id, "arguments": arguments or {}}

    def read_resource(self, uri: str) -> dict[str, object] | str:
        if uri == "repo://status/tasks":
            return {"uri": uri}
        return f"resource:{uri}"


class McpServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text("", encoding="utf-8")
        self.server = build_server(self.repo_root, core=StubCoreService("task-123"))

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_list_tools_exposes_output_schema(self) -> None:
        result = asyncio.run(self.server.request_handlers[types.ListToolsRequest](None))

        self.assertEqual(result.root.tools[0].name, "sisyphus.get_task")
        self.assertEqual(result.root.tools[0].outputSchema["properties"]["task_id"]["type"], "string")

    def test_call_tool_returns_structured_content(self) -> None:
        request = types.CallToolRequest(
            params=types.CallToolRequestParams(
                name="sisyphus.get_task",
                arguments={"task_id": "task-123"},
            )
        )

        result = asyncio.run(self.server.request_handlers[types.CallToolRequest](request))

        self.assertEqual(result.root.structuredContent["task_id"], "task-123")
        self.assertFalse(result.root.isError)

    def test_list_resources_and_templates_split_task_uris(self) -> None:
        resources = asyncio.run(self.server.request_handlers[types.ListResourcesRequest](None))
        templates = asyncio.run(self.server.request_handlers[types.ListResourceTemplatesRequest](None))

        self.assertEqual([str(resource.uri) for resource in resources.root.resources], ["repo://status/tasks"])
        self.assertEqual([template.uriTemplate for template in templates.root.resourceTemplates], ["task://{task_id}/brief"])

    def test_read_resource_preserves_json_and_markdown_mime_types(self) -> None:
        json_request = types.ReadResourceRequest(
            params=types.ReadResourceRequestParams(uri="repo://status/tasks")
        )
        markdown_request = types.ReadResourceRequest(
            params=types.ReadResourceRequestParams(uri="task://task-123/brief")
        )

        json_result = asyncio.run(self.server.request_handlers[types.ReadResourceRequest](json_request))
        markdown_result = asyncio.run(self.server.request_handlers[types.ReadResourceRequest](markdown_request))

        self.assertEqual(json_result.root.contents[0].mimeType, "application/json")
        self.assertEqual(markdown_result.root.contents[0].mimeType, "text/markdown")

    def test_resolve_repo_root_uses_environment_override(self) -> None:
        with mock.patch.dict(os.environ, {"SISYPHUS_REPO_ROOT": str(self.repo_root)}, clear=False):
            resolved = resolve_mcp_repo_root()

        self.assertEqual(resolved, self.repo_root.resolve())

    def test_sisyphus_mcp_server_module_reexports_canonical_entrypoints(self) -> None:
        self.assertIs(legacy_sisyphus_mcp_server.build_server, build_server)
        self.assertIs(legacy_sisyphus_mcp_server.resolve_mcp_repo_root, resolve_mcp_repo_root)

    def test_resolve_repo_root_detects_repo_from_sisyphus_config(self) -> None:
        nested = self.repo_root / "nested" / "child"
        nested.mkdir(parents=True, exist_ok=True)
        (self.repo_root / ".taskflow.toml").unlink()
        (self.repo_root / ".sisyphus.toml").write_text("", encoding="utf-8")

        with mock.patch.dict(os.environ, {"SISYPHUS_REPO_ROOT": str(nested)}, clear=False):
            resolved = resolve_mcp_repo_root()

        self.assertEqual(resolved, self.repo_root.resolve())


if __name__ == "__main__":
    unittest.main()
