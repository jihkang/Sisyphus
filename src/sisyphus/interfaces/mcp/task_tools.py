from __future__ import annotations

from types import MappingProxyType
from pathlib import Path

from ...api import get_task, list_tasks, request_task
from ...config import SisyphusConfig
from ...shared.coerce import optional_str, optional_str_list


def _request_task(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    request_task_fn=request_task,
    **_: object,
) -> dict[str, object]:
    result = request_task_fn(
        repo_root=repo_root,
        config=config,
        message=str(args["message"]),
        title=optional_str(args.get("title")),
        task_type=str(args.get("task_type", "feature")),
        slug=optional_str(args.get("slug")),
        instruction=optional_str(args.get("instruction")),
        agent_id=str(args.get("agent_id", "worker-1")),
        role=str(args.get("role", "worker")),
        provider=str(args.get("provider", "codex")),
        owned_paths=optional_str_list(args.get("owned_paths")),
        provider_args=optional_str_list(args.get("provider_args")),
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


def _list_tasks(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    list_tasks_fn=list_tasks,
    **_: object,
) -> dict[str, object]:
    return {"tasks": list_tasks_fn(repo_root=repo_root, config=config)}


def _get_task(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    get_task_fn=get_task,
    **_: object,
) -> dict[str, object]:
    task_id = str(args["task_id"])
    return {"task": get_task_fn(repo_root=repo_root, task_id=task_id, config=config)}


TOOL_EXECUTORS = MappingProxyType(
    {
        "sisyphus.request_task": _request_task,
        "sisyphus.list_tasks": _list_tasks,
        "sisyphus.get_task": _get_task,
    }
)


def call_task_tool(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    tool_name: str,
    args: dict[str, object],
    request_task_fn=request_task,
    list_tasks_fn=list_tasks,
    get_task_fn=get_task,
) -> dict[str, object] | None:
    executor = TOOL_EXECUTORS.get(tool_name)
    if executor is None:
        return None
    return executor(
        repo_root=repo_root,
        config=config,
        args=args,
        request_task_fn=request_task_fn,
        list_tasks_fn=list_tasks_fn,
        get_task_fn=get_task_fn,
    )


__all__ = ["TOOL_EXECUTORS", "call_task_tool"]
