from __future__ import annotations

from pathlib import Path

from ...application.conformance_records import summarize_task_conformance
from ...bus_jsonl import read_jsonl_events, resolve_event_bus_path
from ...composition.repository_requests import list_tasks
from ...composition.search import search_index_status
from ...config import SisyphusConfig
from ...domain.promotion.state import promotion_summary
from ...metrics import build_value_metrics_report
from .schemas import _mcp_schema_markdown


def read_repo_resource(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    parsed,
    list_tasks_fn=list_tasks,
    resolve_event_bus=resolve_event_bus_path,
    read_events=read_jsonl_events,
    build_metrics=build_value_metrics_report,
    search_status=search_index_status,
    schema_markdown=_mcp_schema_markdown,
) -> dict[str, object] | str | None:
    if parsed.scheme != "repo":
        return None

    if parsed.netloc == "status" and parsed.path == "/tasks":
        return {"tasks": list_tasks_fn(repo_root=repo_root, config=config)}
    if parsed.netloc == "status" and parsed.path == "/conformance":
        tasks = list_tasks_fn(repo_root=repo_root, config=config)
        return {"tasks": [_task_status_projection(task) for task in tasks]}
    if parsed.netloc == "status" and parsed.path == "/board":
        tasks = list_tasks_fn(repo_root=repo_root, config=config)
        path = resolve_event_bus(repo_root, config)
        events = read_events(path, limit=20)
        return _repo_status_board(tasks, events, build_metrics(repo_root, config))
    if parsed.netloc == "status" and parsed.path == "/events":
        path = resolve_event_bus(repo_root, config)
        return {
            "provider": config.event_bus.provider,
            "path": str(path),
            "events": read_events(path, limit=50),
        }
    if parsed.netloc == "status" and parsed.path == "/metrics":
        return build_metrics(repo_root, config)
    if parsed.netloc == "search" and parsed.path == "/status":
        return search_status(repo_root)
    if parsed.netloc == "schema" and parsed.path == "/mcp":
        return schema_markdown()
    return None


def _task_status_projection(task: dict) -> dict[str, object]:
    conformance = summarize_task_conformance(task)
    return {
        "task_id": task.get("id"),
        "slug": task.get("slug"),
        "status": task.get("status"),
        "workflow_phase": task.get("workflow_phase"),
        "plan_status": task.get("plan_status"),
        "spec_status": task.get("spec_status"),
        "updated_at": task.get("updated_at"),
        "promotion": promotion_summary(task),
        "conformance": {
            "status": conformance.get("status"),
            "last_spec_anchor_at": conformance.get("last_spec_anchor_at"),
            "last_checkpoint_type": conformance.get("last_checkpoint_type"),
            "drift_count": conformance.get("drift_count"),
            "last_warning": conformance.get("last_warning"),
            "last_failure": conformance.get("last_failure"),
            "summary": conformance.get("summary"),
        },
    }


def _repo_status_board(
    tasks: list[dict],
    events: list[dict[str, object]],
    metrics: dict[str, object] | None = None,
) -> dict[str, object]:
    rows = [_task_status_projection(task) for task in tasks]
    counts = {"green": 0, "yellow": 0, "red": 0, "unknown": 0}
    for row in rows:
        status = str(row.get("conformance", {}).get("status") or "unknown").lower()
        if status not in counts:
            counts["unknown"] += 1
        else:
            counts[status] += 1
    return {
        "summary": {
            "task_count": len(rows),
            "green": counts["green"],
            "yellow": counts["yellow"],
            "red": counts["red"],
            "unknown": counts["unknown"],
        },
        "tasks": rows,
        "recent_events": events,
        "metrics": metrics,
    }


__all__ = ["read_repo_resource"]
