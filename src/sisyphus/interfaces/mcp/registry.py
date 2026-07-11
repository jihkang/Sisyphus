from __future__ import annotations

from typing import Literal

ToolGroup = Literal["task", "search", "evolution", "promotion", "workflow"]

TASK_TOOL_NAMES = frozenset(
    {
        "sisyphus.request_task",
        "sisyphus.list_tasks",
        "sisyphus.get_task",
    }
)
SEARCH_TOOL_NAMES = frozenset(
    {
        "sisyphus.search_index_rebuild",
        "sisyphus.search",
        "sisyphus.context_build",
    }
)
EVOLUTION_TOOL_NAMES = frozenset(
    {
        "sisyphus.evolution_execute",
        "sisyphus.evolution_followup_request",
        "sisyphus.evolution_decide",
        "sisyphus.evolution_run",
        "sisyphus.evolution_status",
        "sisyphus.evolution_report",
        "sisyphus.evolution_compare",
    }
)
PROMOTION_TOOL_NAMES = frozenset(
    {
        "sisyphus.record_merged_pr",
        "sisyphus.execute_promotion",
    }
)
WORKFLOW_TOOL_NAMES = frozenset(
    {
        "sisyphus.plan_approve",
        "sisyphus.plan_request_changes",
        "sisyphus.plan_revise",
        "sisyphus.spec_freeze",
        "sisyphus.subtasks_generate",
        "sisyphus.verify_task",
        "sisyphus.close_task",
        "sisyphus.list_agents",
        "sisyphus.daemon_once",
    }
)

TOOL_GROUP_BY_NAME: dict[str, ToolGroup] = {
    **{name: "task" for name in TASK_TOOL_NAMES},
    **{name: "search" for name in SEARCH_TOOL_NAMES},
    **{name: "evolution" for name in EVOLUTION_TOOL_NAMES},
    **{name: "promotion" for name in PROMOTION_TOOL_NAMES},
    **{name: "workflow" for name in WORKFLOW_TOOL_NAMES},
}


def tool_group_for(tool_name: str) -> ToolGroup | None:
    return TOOL_GROUP_BY_NAME.get(tool_name)


def registered_tool_names() -> set[str]:
    return set(TOOL_GROUP_BY_NAME)


__all__ = [
    "EVOLUTION_TOOL_NAMES",
    "PROMOTION_TOOL_NAMES",
    "SEARCH_TOOL_NAMES",
    "TASK_TOOL_NAMES",
    "TOOL_GROUP_BY_NAME",
    "ToolGroup",
    "WORKFLOW_TOOL_NAMES",
    "registered_tool_names",
    "tool_group_for",
]
