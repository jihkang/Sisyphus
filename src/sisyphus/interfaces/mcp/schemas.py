from __future__ import annotations

from .resources import mcp_resource_definitions
from .tools import mcp_tool_definitions


def _mcp_schema_markdown() -> str:
    lines = [
        "# Sisyphus MCP Schema",
        "",
        "## Tools",
        "",
    ]
    for tool in mcp_tool_definitions():
        lines.append(f"- `{tool['name']}`: {tool['description']}")
        schema = tool.get("inputSchema")
        if isinstance(schema, dict):
            required = schema.get("required", [])
            if required:
                lines.append(f"  required: {', '.join(str(item) for item in required)}")
        output_schema = tool.get("outputSchema")
        if isinstance(output_schema, dict):
            properties = output_schema.get("properties", {})
            if isinstance(properties, dict) and properties:
                lines.append(f"  returns: {', '.join(str(key) for key in properties.keys())}")
    lines.extend(
        [
            "",
            "## Resources",
            "",
        ]
    )
    for resource in mcp_resource_definitions():
        lines.append(f"- `{resource['uri']}`: {resource['description']}")
    lines.extend(
        [
            "",
            "## Conformance Colors",
            "",
            "- `green`: spec aligned",
            "- `yellow`: minor drift or unresolved clarification",
            "- `red`: blocking drift",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "_mcp_schema_markdown",
]
