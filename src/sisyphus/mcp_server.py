from __future__ import annotations

import json
import os
from pathlib import Path
import re

import anyio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.stdio import stdio_server

from .discovery import detect_repo_root
from .mcp_core import SisyphusMcpCoreService


SERVER_NAME = "sisyphus"
SERVER_VERSION = "0.1.0"
DEBUG_ENV_VAR = "SISYPHUS_MCP_DEBUG_LOG"
TASK_TEMPLATE_TOKEN = "<task-id>"


def resolve_mcp_repo_root() -> Path:
    explicit = os.environ.get("SISYPHUS_REPO_ROOT")
    if explicit:
        return detect_repo_root(Path(explicit).resolve())
    return detect_repo_root(Path.cwd())


def build_server(repo_root: Path, core: SisyphusMcpCoreService | None = None) -> Server:
    service = core or SisyphusMcpCoreService(repo_root)
    server = Server(SERVER_NAME, version=SERVER_VERSION)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        _debug_log("list_tools")
        return [_to_tool(tool) for tool in service.list_tools()]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, object] | None) -> dict[str, object]:
        _debug_log(f"call_tool name={name}")
        return service.call_tool(name, arguments)

    @server.list_resources()
    async def list_resources() -> list[types.Resource]:
        _debug_log("list_resources")
        return [_to_resource(resource) for resource in service.list_resources() if not _is_template_uri(str(resource["uri"]))]

    @server.list_resource_templates()
    async def list_resource_templates() -> list[types.ResourceTemplate]:
        _debug_log("list_resource_templates")
        return [
            _to_resource_template(resource)
            for resource in service.list_resources()
            if _is_template_uri(str(resource["uri"]))
        ]

    @server.read_resource()
    async def read_resource(uri: types.AnyUrl) -> list[ReadResourceContents]:
        uri_str = str(uri)
        _debug_log(f"read_resource uri={uri_str}")
        result = service.read_resource(uri_str)
        if isinstance(result, str):
            return [ReadResourceContents(content=result, mime_type="text/markdown")]
        return [ReadResourceContents(content=json.dumps(result, indent=2), mime_type="application/json")]

    return server


async def run_stdio_server(repo_root: Path | None = None) -> None:
    resolved_repo_root = repo_root or resolve_mcp_repo_root()
    _debug_log(f"resolved_repo_root repo_root={resolved_repo_root}")
    server = build_server(resolved_repo_root)
    _debug_log(f"server_started repo_root={resolved_repo_root}")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )


def main() -> int:
    _debug_log("main_start")
    try:
        anyio.run(run_stdio_server)
    except Exception as exc:
        _debug_log(f"main_error error={exc}")
        raise
    _debug_log("main_exit")
    return 0


def _to_tool(definition: dict[str, object]) -> types.Tool:
    input_schema = dict(definition.get("inputSchema") or {"type": "object", "properties": {}, "additionalProperties": False})
    output_schema = definition.get("outputSchema")
    return types.Tool(
        name=str(definition["name"]),
        description=str(definition.get("description") or ""),
        inputSchema=input_schema,
        outputSchema=dict(output_schema) if isinstance(output_schema, dict) else None,
    )


def _to_resource(definition: dict[str, object]) -> types.Resource:
    uri = str(definition["uri"])
    return types.Resource(
        uri=uri,
        name=_resource_name(uri),
        description=str(definition.get("description") or ""),
        mimeType=_resource_mime_type(uri),
    )


def _to_resource_template(definition: dict[str, object]) -> types.ResourceTemplate:
    uri = str(definition["uri"])
    uri_template = uri.replace(TASK_TEMPLATE_TOKEN, "{task_id}")
    return types.ResourceTemplate(
        uriTemplate=uri_template,
        name=_resource_name(uri_template),
        description=str(definition.get("description") or ""),
        mimeType=_resource_mime_type(uri),
    )


def _is_template_uri(uri: str) -> bool:
    return TASK_TEMPLATE_TOKEN in uri


def _resource_name(uri: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", uri).strip("-").lower()
    return normalized or "resource"


def _resource_mime_type(uri: str) -> str:
    if uri == "repo://schema/mcp":
        return "text/markdown"
    if any(uri.endswith(suffix) for suffix in ("/brief", "/plan", "/verify", "/log")):
        return "text/markdown"
    return "application/json"


def _debug_log(message: str) -> None:
    path = os.environ.get(DEBUG_ENV_VAR)
    if not path:
        return
    try:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(f"[mcp_server] {message}\n")
    except OSError:
        pass


__all__ = ["build_server", "main", "resolve_mcp_repo_root", "run_stdio_server"]


if __name__ == "__main__":
    raise SystemExit(main())
