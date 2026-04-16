from __future__ import annotations

import importlib
import sys

from taskflow import (
    QueuedConversation,
    TaskRequestResult,
    __version__,
    get_task,
    list_tasks,
    queue_conversation,
    request_task,
    run_until_stable,
)

__all__ = [
    "__version__",
    "QueuedConversation",
    "TaskRequestResult",
    "get_task",
    "list_tasks",
    "queue_conversation",
    "request_task",
    "run_until_stable",
]

_ALIASED_SUBMODULES = (
    "agent_runtime",
    "agents",
    "api",
    "audit",
    "bus",
    "bus_jsonl",
    "closeout",
    "codex_prompt",
    "config",
    "conformance",
    "creation",
    "daemon",
    "discipline",
    "discord_bot",
    "discovery",
    "events",
    "gitops",
    "mcp_adapter",
    "mcp_core",
    "paths",
    "planning",
    "provider_wrapper",
    "service",
    "state",
    "strategy",
    "templates",
    "utils",
    "workflow",
)


def _install_submodule_aliases() -> None:
    for submodule_name in _ALIASED_SUBMODULES:
        module = importlib.import_module(f"taskflow.{submodule_name}")
        alias = f"{__name__}.{submodule_name}"
        sys.modules.setdefault(alias, module)
        globals().setdefault(submodule_name, module)


_install_submodule_aliases()
