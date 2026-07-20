from __future__ import annotations

from pathlib import Path

from ..application.repository_status import repository_status_board, task_status_projection
from ..infra.config.loader import SisyphusConfig
from ..infra.events import read_jsonl_events, resolve_event_bus_path
from .metrics import build_value_metrics_report
from .repository_requests import list_tasks


def repository_tasks_status(repo_root: Path, config: SisyphusConfig) -> dict[str, object]:
    return {"tasks": list_tasks(repo_root=repo_root, config=config)}


def repository_conformance_status(
    repo_root: Path,
    config: SisyphusConfig,
) -> dict[str, object]:
    tasks = list_tasks(repo_root=repo_root, config=config)
    return {"tasks": [task_status_projection(task) for task in tasks]}


def repository_board_status(repo_root: Path, config: SisyphusConfig) -> dict[str, object]:
    tasks = list_tasks(repo_root=repo_root, config=config)
    path = resolve_event_bus_path(repo_root, config)
    return repository_status_board(
        tasks,
        read_jsonl_events(path, limit=20),
        build_value_metrics_report(repo_root, config),
    )


def repository_events_status(repo_root: Path, config: SisyphusConfig) -> dict[str, object]:
    path = resolve_event_bus_path(repo_root, config)
    return {
        "provider": config.event_bus.provider,
        "path": str(path),
        "events": read_jsonl_events(path, limit=50),
    }


__all__ = [
    "build_value_metrics_report",
    "repository_board_status",
    "repository_conformance_status",
    "repository_events_status",
    "repository_tasks_status",
]
