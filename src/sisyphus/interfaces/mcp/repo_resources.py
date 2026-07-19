from __future__ import annotations

from pathlib import Path

from ...composition.repository_status import (
    build_value_metrics_report,
    repository_board_status,
    repository_conformance_status,
    repository_events_status,
    repository_tasks_status,
)
from ...composition.search import search_index_status
from ...config import SisyphusConfig
from .schemas import _mcp_schema_markdown


def read_repo_resource(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    parsed,
    tasks_status=repository_tasks_status,
    conformance_status=repository_conformance_status,
    board_status=repository_board_status,
    events_status=repository_events_status,
    metrics_status=build_value_metrics_report,
    search_status=search_index_status,
    schema_markdown=_mcp_schema_markdown,
) -> dict[str, object] | str | None:
    if parsed.scheme != "repo":
        return None

    if parsed.netloc == "status" and parsed.path == "/tasks":
        return tasks_status(repo_root, config)
    if parsed.netloc == "status" and parsed.path == "/conformance":
        return conformance_status(repo_root, config)
    if parsed.netloc == "status" and parsed.path == "/board":
        return board_status(repo_root, config)
    if parsed.netloc == "status" and parsed.path == "/events":
        return events_status(repo_root, config)
    if parsed.netloc == "status" and parsed.path == "/metrics":
        return metrics_status(repo_root, config)
    if parsed.netloc == "search" and parsed.path == "/status":
        return search_status(repo_root)
    if parsed.netloc == "schema" and parsed.path == "/mcp":
        return schema_markdown()
    return None


__all__ = ["read_repo_resource"]
