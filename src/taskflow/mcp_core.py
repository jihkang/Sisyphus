from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from .agents import list_agents
from .api import get_task, list_tasks, request_task
from .audit import run_verify
from .bus_jsonl import read_jsonl_events, resolve_event_bus_path
from .closeout import run_close
from .config import load_config
from .conformance import ensure_task_conformance_defaults, summarize_subtask_conformance, summarize_task_conformance
from .daemon import run_daemon
from .planning import (
    approve_task_plan,
    freeze_task_spec,
    generate_subtasks,
    request_plan_changes,
    revise_task_plan,
)
from .state import load_task_record


class SisyphusMcpCoreService:
    """Core MCP-facing service that resolves tools and resources for a repo.

    The MCP gateway should depend on this service, not on Sisyphus internals
    directly. That keeps protocol/transport concerns separate from business
    logic and persistence access.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def list_tools(self) -> list[dict[str, object]]:
        return mcp_tool_definitions()

    def list_resources(self) -> list[dict[str, object]]:
        return mcp_resource_definitions()

    def call_tool(self, tool_name: str, arguments: dict[str, object] | None = None) -> dict[str, object]:
        args = arguments or {}
        config = load_config(self.repo_root)

        if tool_name == "sisyphus.request_task":
            result = request_task(
                repo_root=self.repo_root,
                config=config,
                message=str(args["message"]),
                title=_optional_str(args.get("title")),
                task_type=str(args.get("task_type", "feature")),
                slug=_optional_str(args.get("slug")),
                instruction=_optional_str(args.get("instruction")),
                agent_id=str(args.get("agent_id", "worker-1")),
                role=str(args.get("role", "worker")),
                provider=str(args.get("provider", "codex")),
                owned_paths=_str_list(args.get("owned_paths")),
                provider_args=_str_list(args.get("provider_args")),
                auto_run=bool(args.get("auto_run", True)),
            )
            return {
                "ok": result.ok,
                "event_id": result.event_id,
                "task_id": result.task_id,
                "event_status": result.event_status,
                "orchestrated": result.orchestrated,
                "error": result.error,
            }

        if tool_name == "sisyphus.list_tasks":
            return {"tasks": list_tasks(repo_root=self.repo_root, config=config)}

        if tool_name == "sisyphus.get_task":
            task_id = str(args["task_id"])
            return {"task": get_task(repo_root=self.repo_root, task_id=task_id, config=config)}

        if tool_name == "sisyphus.plan_approve":
            outcome = approve_task_plan(
                repo_root=self.repo_root,
                config=config,
                task_id=str(args["task_id"]),
                reviewer=str(args.get("reviewer", "operator")),
                notes=_optional_str(args.get("notes")),
            )
            return {"task_id": outcome.task_id, "plan_status": outcome.plan_status, "task_status": outcome.task_status, "gates": outcome.gates}

        if tool_name == "sisyphus.plan_request_changes":
            outcome = request_plan_changes(
                repo_root=self.repo_root,
                config=config,
                task_id=str(args["task_id"]),
                reviewer=str(args.get("reviewer", "operator")),
                notes=_optional_str(args.get("notes")),
            )
            return {"task_id": outcome.task_id, "plan_status": outcome.plan_status, "task_status": outcome.task_status, "gates": outcome.gates}

        if tool_name == "sisyphus.plan_revise":
            outcome = revise_task_plan(
                repo_root=self.repo_root,
                config=config,
                task_id=str(args["task_id"]),
                author=str(args.get("author", "operator")),
                notes=_optional_str(args.get("notes")),
            )
            return {"task_id": outcome.task_id, "plan_status": outcome.plan_status, "task_status": outcome.task_status, "gates": outcome.gates}

        if tool_name == "sisyphus.spec_freeze":
            outcome = freeze_task_spec(
                repo_root=self.repo_root,
                config=config,
                task_id=str(args["task_id"]),
                reviewer=str(args.get("reviewer", "operator")),
                notes=_optional_str(args.get("notes")),
            )
            return {
                "task_id": outcome.task_id,
                "spec_status": outcome.spec_status,
                "task_status": outcome.task_status,
                "workflow_phase": outcome.workflow_phase,
            }

        if tool_name == "sisyphus.subtasks_generate":
            outcome = generate_subtasks(repo_root=self.repo_root, config=config, task_id=str(args["task_id"]))
            return {"task_id": outcome.task_id, "workflow_phase": outcome.workflow_phase, "subtasks": outcome.subtasks}

        if tool_name == "sisyphus.verify_task":
            outcome = run_verify(repo_root=self.repo_root, config=config, task_id=str(args["task_id"]))
            return {
                "task_id": outcome.task_id,
                "status": outcome.status,
                "stage": outcome.stage,
                "gates": outcome.gates,
                "audit_attempts": outcome.audit_attempts,
            }

        if tool_name == "sisyphus.close_task":
            outcome = run_close(
                repo_root=self.repo_root,
                config=config,
                task_id=str(args["task_id"]),
                allow_dirty=bool(args.get("allow_dirty", False)),
            )
            return {
                "task_id": outcome.task_id,
                "status": outcome.status,
                "closed": outcome.closed,
                "allow_dirty": outcome.allow_dirty,
                "gates": outcome.gates,
            }

        if tool_name == "sisyphus.list_agents":
            task_id = _optional_str(args.get("task_id"))
            stale_after_seconds = int(args.get("stale_after_seconds", 900))
            return {
                "agents": list_agents(
                    repo_root=self.repo_root,
                    config=config,
                    task_id=task_id,
                    stale_after_seconds=stale_after_seconds,
                )
            }

        if tool_name == "sisyphus.daemon_once":
            stats = run_daemon(
                repo_root=self.repo_root,
                config=config,
                once=True,
                poll_interval_seconds=int(args.get("poll_interval_seconds", 1)),
                max_events=int(args["max_events"]) if args.get("max_events") is not None else None,
            )
            return {
                "processed": stats.processed,
                "failed": stats.failed,
                "skipped": stats.skipped,
                "orchestrated": stats.orchestrated,
            }

        raise ValueError(f"unsupported MCP tool: {tool_name}")

    def read_resource(self, uri: str) -> dict[str, object] | str:
        parsed = urlparse(uri)
        config = load_config(self.repo_root)

        if parsed.scheme == "repo" and parsed.netloc == "status" and parsed.path == "/tasks":
            return {"tasks": list_tasks(repo_root=self.repo_root, config=config)}
        if parsed.scheme == "repo" and parsed.netloc == "status" and parsed.path == "/conformance":
            tasks = list_tasks(repo_root=self.repo_root, config=config)
            return {"tasks": [_task_status_projection(task) for task in tasks]}
        if parsed.scheme == "repo" and parsed.netloc == "status" and parsed.path == "/board":
            tasks = list_tasks(repo_root=self.repo_root, config=config)
            path = resolve_event_bus_path(self.repo_root, config)
            events = read_jsonl_events(path, limit=20)
            return _repo_status_board(tasks, events)
        if parsed.scheme == "repo" and parsed.netloc == "status" and parsed.path == "/events":
            path = resolve_event_bus_path(self.repo_root, config)
            return {
                "provider": config.event_bus.provider,
                "path": str(path),
                "events": read_jsonl_events(path, limit=50),
            }
        if parsed.scheme == "repo" and parsed.netloc == "schema" and parsed.path == "/mcp":
            return _mcp_schema_markdown()

        if parsed.scheme != "task":
            raise ValueError(f"unsupported MCP resource URI: {uri}")

        task_id = parsed.netloc
        resource_name = parsed.path.lstrip("/")
        task, task_file = load_task_record(repo_root=self.repo_root, task_dir_name=config.task_dir, task_id=task_id)
        task_dir = task_file.parent

        if resource_name == "record":
            return {"task": task}
        if resource_name == "conformance":
            return {"conformance": summarize_task_conformance(task)}
        if resource_name == "timeline":
            return _task_timeline_resource(task)
        if resource_name == "agents":
            return {
                "agents": list_agents(
                    repo_root=self.repo_root,
                    config=config,
                    task_id=task_id,
                )
            }

        doc_key = _resource_doc_key(resource_name, task)
        if doc_key is None:
            raise ValueError(f"unsupported task resource `{resource_name}` for task://{task_id}")

        doc_name = task["docs"].get(doc_key)
        if not doc_name:
            raise FileNotFoundError(f"task `{task_id}` does not define document `{doc_key}`")
        doc_path = task_dir / str(doc_name)
        if not doc_path.exists():
            raise FileNotFoundError(f"task document not found: {doc_path}")
        return doc_path.read_text(encoding="utf-8")


def mcp_tool_definitions() -> list[dict[str, object]]:
    return [
        {
            "name": "sisyphus.request_task",
            "description": "Create a repository-local task from a natural-language request.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "title": {"type": "string"},
                    "task_type": {"type": "string", "enum": ["feature", "issue"]},
                    "slug": {"type": "string"},
                    "instruction": {"type": "string"},
                    "agent_id": {"type": "string"},
                    "role": {"type": "string"},
                    "provider": {"type": "string"},
                    "owned_paths": {"type": "array", "items": {"type": "string"}},
                    "provider_args": {"type": "array", "items": {"type": "string"}},
                    "auto_run": {"type": "boolean"},
                },
                "required": ["message"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "event_id": {"type": ["string", "null"]},
                    "task_id": {"type": ["string", "null"]},
                    "event_status": {"type": ["string", "null"]},
                    "orchestrated": {"type": "integer"},
                    "error": {"type": ["string", "null"]},
                },
            },
        },
        {
            "name": "sisyphus.list_tasks",
            "description": "List repository tasks.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"tasks": {"type": "array"}}},
        },
        {
            "name": "sisyphus.get_task",
            "description": "Read a single task record.",
            "inputSchema": {
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task": {"type": "object"}}},
        },
        {
            "name": "sisyphus.plan_approve",
            "description": "Approve a task plan.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "reviewer": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "plan_status": {"type": "string"}, "task_status": {"type": "string"}, "gates": {"type": "array"}}},
        },
        {
            "name": "sisyphus.plan_request_changes",
            "description": "Request plan changes for a task.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "reviewer": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "plan_status": {"type": "string"}, "task_status": {"type": "string"}, "gates": {"type": "array"}}},
        },
        {
            "name": "sisyphus.plan_revise",
            "description": "Revise a task plan after review.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "author": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "plan_status": {"type": "string"}, "task_status": {"type": "string"}, "gates": {"type": "array"}}},
        },
        {
            "name": "sisyphus.spec_freeze",
            "description": "Freeze a task spec.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "reviewer": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "spec_status": {"type": "string"}, "task_status": {"type": "string"}, "workflow_phase": {"type": "string"}}},
        },
        {
            "name": "sisyphus.subtasks_generate",
            "description": "Generate subtasks from the current strategy.",
            "inputSchema": {
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "workflow_phase": {"type": "string"}, "subtasks": {"type": "array"}}},
        },
        {
            "name": "sisyphus.verify_task",
            "description": "Run verification for a task.",
            "inputSchema": {
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "status": {"type": "string"}, "stage": {"type": "string"}, "gates": {"type": "array"}, "audit_attempts": {"type": "integer"}}},
        },
        {
            "name": "sisyphus.close_task",
            "description": "Close a verified task.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "allow_dirty": {"type": "boolean"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "status": {"type": "string"}, "closed": {"type": "boolean"}, "allow_dirty": {"type": "boolean"}, "gates": {"type": "array"}}},
        },
        {
            "name": "sisyphus.list_agents",
            "description": "List tracked agents for the repo or a task.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "stale_after_seconds": {"type": "integer", "minimum": 1},
                },
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"agents": {"type": "array"}}},
        },
        {
            "name": "sisyphus.daemon_once",
            "description": "Process inbox events and run one daemon cycle.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "poll_interval_seconds": {"type": "integer", "minimum": 1},
                    "max_events": {"type": "integer", "minimum": 1},
                },
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"processed": {"type": "integer"}, "failed": {"type": "integer"}, "skipped": {"type": "integer"}, "orchestrated": {"type": "integer"}}},
        },
    ]


def mcp_resource_definitions() -> list[dict[str, object]]:
    return [
        {"uri": "repo://status/tasks", "description": "Structured list of all tasks in the repository."},
        {"uri": "repo://status/conformance", "description": "Repository-wide task conformance board."},
        {"uri": "repo://status/board", "description": "Operator-focused board with conformance summary and recent events."},
        {"uri": "repo://status/events", "description": "Recent event bus envelopes from the repository event log."},
        {"uri": "repo://schema/mcp", "description": "Human-readable MCP tool and resource schema for Sisyphus."},
        {"uri": "task://<task-id>/record", "description": "Raw task record JSON."},
        {"uri": "task://<task-id>/conformance", "description": "Task-level conformance summary."},
        {"uri": "task://<task-id>/timeline", "description": "Task and subtask conformance/drift timeline."},
        {"uri": "task://<task-id>/brief", "description": "Task brief markdown."},
        {"uri": "task://<task-id>/plan", "description": "Task plan markdown."},
        {"uri": "task://<task-id>/verify", "description": "Task verification markdown."},
        {"uri": "task://<task-id>/log", "description": "Task log markdown."},
        {"uri": "task://<task-id>/agents", "description": "Tracked agent records for a task."},
    ]


def _resource_doc_key(resource_name: str, task: dict) -> str | None:
    if resource_name == "brief":
        return "brief"
    if resource_name == "plan":
        if task.get("type") == "feature":
            return "plan"
        return "fix_plan"
    if resource_name == "verify":
        return "verify"
    if resource_name == "log":
        return "log"
    if resource_name == "repro" and task.get("type") == "issue":
        return "repro"
    return None


def _optional_str(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _str_list(value: object) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise TypeError(f"expected list value, got: {type(value).__name__}")
    return [str(item) for item in value]


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


def _repo_status_board(tasks: list[dict], events: list[dict[str, object]]) -> dict[str, object]:
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
    }


def _task_timeline_resource(task: dict) -> dict[str, object]:
    ensure_task_conformance_defaults(task)
    task_summary = summarize_task_conformance(task)
    task_history = list(task.get("conformance", {}).get("history", []))
    subtasks = task.get("subtasks", [])
    subtask_timelines: list[dict[str, object]] = []
    if isinstance(subtasks, list):
        for subtask in subtasks:
            if not isinstance(subtask, dict):
                continue
            subtask_timelines.append(
                {
                    "subtask_id": subtask.get("id"),
                    "title": subtask.get("title"),
                    "status": summarize_subtask_conformance(subtask).get("status"),
                    "history": list(subtask.get("conformance", {}).get("history", [])),
                }
            )
    return {
        "task_id": task.get("id"),
        "summary": {
            "status": task_summary.get("status"),
            "drift_count": task_summary.get("drift_count"),
            "warning_count": task_summary.get("warning_count"),
            "unresolved_warning_count": task_summary.get("unresolved_warning_count"),
            "last_checkpoint_type": task_summary.get("last_checkpoint_type"),
            "last_checkpoint_at": task_summary.get("last_checkpoint_at"),
            "last_warning": task_summary.get("last_warning"),
            "last_failure": task_summary.get("last_failure"),
        },
        "task_history": task_history,
        "subtasks": subtask_timelines,
    }
