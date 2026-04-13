from __future__ import annotations

from pathlib import Path

from .mcp_core import SisyphusMcpCoreService, mcp_resource_definitions, mcp_tool_definitions


def list_mcp_tools() -> list[dict[str, object]]:
    return mcp_tool_definitions()


def list_mcp_resources() -> list[dict[str, object]]:
    return mcp_resource_definitions()


def call_mcp_tool(repo_root: Path, tool_name: str, arguments: dict[str, object] | None = None) -> dict[str, object]:
    return SisyphusMcpCoreService(repo_root).call_tool(tool_name, arguments)


def read_mcp_resource(repo_root: Path, uri: str) -> dict[str, object] | str:
    return SisyphusMcpCoreService(repo_root).read_resource(uri)
