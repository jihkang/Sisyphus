from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from ...artifact_resources import is_feature_task_artifact_resource, read_feature_task_artifact_resource
from ...api import execute_promotion, get_task, list_tasks, record_merged_pull_request, request_task
from ...audit import run_verify
from ...bus_jsonl import read_jsonl_events, resolve_event_bus_path
from ...closeout import run_close
from ...config import load_config
from ...context_pack import build_and_persist_context_pack, read_context_pack
from ...daemon import run_daemon
from ...episode_trace import append_episode_step, build_episode_step, default_episode_id, next_episode_step
from ...evolution.operator import (
    evaluate_evolution_followup_decision,
    request_evolution_followup,
)
from ...evolution.surface import (
    compare_evolution_runs,
    execute_evolution_surface,
    load_evolution_run_artifacts,
    render_evolution_run_compare,
    render_evolution_run_overview,
    render_evolution_run_report,
    render_evolution_run_status,
)
from ...planning import (
    approve_task_plan,
    freeze_task_spec,
    generate_subtasks,
    request_plan_changes,
    revise_task_plan,
)
from ...metrics import build_value_metrics_report
from ...observation import build_task_observation
from ...retrieval import retrieve_documents
from ...search_index import read_search_index, rebuild_search_index, search_index_status
from ...spec_validation import validate_task_spec
from ...state import load_task_record
import sisyphus.interfaces.mcp.evolution as evolution_handlers
import sisyphus.interfaces.mcp.promotion_tools as promotion_tools
import sisyphus.interfaces.mcp.repo_resources as repo_resources
import sisyphus.interfaces.mcp.search_tools as search_tools
import sisyphus.interfaces.mcp.task_resources as task_resources
import sisyphus.interfaces.mcp.task_tools as task_tools
import sisyphus.interfaces.mcp.workflow_tools as workflow_tools
from ..agent_queries import list_agents
from .registry import tool_group_for
from .resources import mcp_resource_definitions
from .schemas import _mcp_schema_markdown
from .tools import mcp_tool_definitions


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
        task_id = _trace_task_id(tool_name, args)
        if task_id and _trace_tool_enabled(tool_name):
            return self._call_tool_with_episode_trace(tool_name, args, config, task_id)
        return self._call_tool_inner(tool_name, args, config)

    def _call_tool_with_episode_trace(
        self,
        tool_name: str,
        args: dict[str, object],
        config: object,
        task_id: str,
    ) -> dict[str, object]:
        task_dir_name = getattr(config, "task_dir", None)
        if task_dir_name is None:
            return self._call_tool_inner(tool_name, args, config)
        try:
            state_before, task_file = load_task_record(
                repo_root=self.repo_root,
                task_dir_name=task_dir_name,
                task_id=task_id,
            )
            task_dir = task_file.parent
        except FileNotFoundError:
            return self._call_tool_inner(tool_name, args, config)

        observation_before = build_task_observation(state_before, task_dir)
        result: dict[str, object] | None = None
        error: Exception | None = None
        try:
            result = self._call_tool_inner(tool_name, args, config)
            return result
        except Exception as exc:
            error = exc
            result = {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            raise
        finally:
            try:
                state_after, _ = load_task_record(
                    repo_root=self.repo_root,
                    task_dir_name=task_dir_name,
                    task_id=task_id,
                )
            except FileNotFoundError:
                state_after = state_before
            actor = _trace_actor(args)
            episode_id = default_episode_id(task_id, actor_id=str(actor.get("agent_id", "mcp")))
            trace_result = dict(result or {})
            if error is not None:
                trace_result.setdefault("ok", False)
            append_episode_step(
                task_dir,
                build_episode_step(
                    episode_id=episode_id,
                    task_id=task_id,
                    step=next_episode_step(task_dir, episode_id),
                    observation=observation_before,
                    action_name=tool_name,
                    arguments=args,
                    result=trace_result,
                    state_before=state_before,
                    state_after=state_after,
                    actor=actor,
                ),
            )

    def _call_tool_inner(self, tool_name: str, args: dict[str, object], config: object) -> dict[str, object]:
        group = tool_group_for(tool_name)
        if group is None:
            raise ValueError(f"unsupported MCP tool: {tool_name}")

        if group == "task":
            payload = task_tools.call_task_tool(
                repo_root=self.repo_root,
                config=config,
                tool_name=tool_name,
                args=args,
                request_task_fn=request_task,
                list_tasks_fn=list_tasks,
                get_task_fn=get_task,
            )
        elif group == "search":
            payload = search_tools.call_search_tool(
                repo_root=self.repo_root,
                config=config,
                tool_name=tool_name,
                args=args,
                rebuild_index=rebuild_search_index,
                read_index=read_search_index,
                retrieve=retrieve_documents,
                build_context_pack=build_and_persist_context_pack,
            )
        elif group == "evolution":
            payload = evolution_handlers.call_evolution_tool(
                repo_root=self.repo_root,
                config=config,
                tool_name=tool_name,
                args=args,
                load_artifacts=load_evolution_run_artifacts,
                render_overview=render_evolution_run_overview,
                render_status=render_evolution_run_status,
                render_report=render_evolution_run_report,
                compare_runs=compare_evolution_runs,
                render_compare=render_evolution_run_compare,
                execute_surface=execute_evolution_surface,
                request_followup=request_evolution_followup,
                decide_followup=evaluate_evolution_followup_decision,
            )
        elif group == "promotion":
            payload = promotion_tools.call_promotion_tool(
                repo_root=self.repo_root,
                config=config,
                tool_name=tool_name,
                args=args,
                record_merged_pr=record_merged_pull_request,
                execute_promotion_fn=execute_promotion,
            )
        else:
            payload = workflow_tools.call_workflow_tool(
                repo_root=self.repo_root,
                config=config,
                tool_name=tool_name,
                args=args,
                approve_plan=approve_task_plan,
                request_changes=request_plan_changes,
                revise_plan=revise_task_plan,
                freeze_spec=freeze_task_spec,
                validate_spec_fn=validate_task_spec,
                generate_subtasks_fn=generate_subtasks,
                verify_task=run_verify,
                close_task=run_close,
                list_agents_fn=list_agents,
                run_daemon_fn=run_daemon,
            )
        if payload is None:
            raise ValueError(f"registered MCP tool has no handler payload: {tool_name}")
        return payload

    def read_resource(self, uri: str) -> dict[str, object] | str:
        parsed = urlparse(uri)
        config = load_config(self.repo_root)

        repo_payload = repo_resources.read_repo_resource(
            repo_root=self.repo_root,
            config=config,
            parsed=parsed,
            list_tasks_fn=list_tasks,
            resolve_event_bus=resolve_event_bus_path,
            read_events=read_jsonl_events,
            build_metrics=build_value_metrics_report,
            search_status=search_index_status,
            schema_markdown=_mcp_schema_markdown,
        )
        if repo_payload is not None:
            return repo_payload

        if parsed.scheme == "evolution":
            return evolution_handlers.read_evolution_resource(
                self.repo_root,
                parsed,
                load_artifacts=load_evolution_run_artifacts,
                compare_runs=compare_evolution_runs,
                render_compare=render_evolution_run_compare,
                render_overview=render_evolution_run_overview,
                render_status=render_evolution_run_status,
                render_report=render_evolution_run_report,
            )
        if parsed.scheme == "context":
            return read_context_pack(self.repo_root, parsed.netloc)

        if parsed.scheme == "task":
            return task_resources.read_task_resource(
                repo_root=self.repo_root,
                config=config,
                parsed=parsed,
                load_record=load_task_record,
                list_agents_fn=list_agents,
                is_artifact_resource=is_feature_task_artifact_resource,
                read_artifact_resource=read_feature_task_artifact_resource,
            )

        raise ValueError(f"unsupported MCP resource URI: {uri}")


_TRACEABLE_TASK_TOOLS = {
    "sisyphus.plan_approve",
    "sisyphus.plan_request_changes",
    "sisyphus.plan_revise",
    "sisyphus.spec_freeze",
    "sisyphus.spec_validate",
    "sisyphus.subtasks_generate",
    "sisyphus.verify_task",
    "sisyphus.close_task",
    "sisyphus.execute_promotion",
    "sisyphus.record_merged_pr",
    "sisyphus.evolution_decide",
}


def _trace_tool_enabled(tool_name: str) -> bool:
    return tool_name in _TRACEABLE_TASK_TOOLS


def _trace_task_id(tool_name: str, args: dict[str, object]) -> str | None:
    value = args.get("task_id")
    if value is None:
        return None
    task_id = str(value).strip()
    if not task_id:
        return None
    return task_id


def _trace_actor(args: dict[str, object]) -> dict[str, object]:
    actor: dict[str, object] = {
        "interface": "mcp",
        "agent_id": str(args.get("agent_id") or "mcp"),
    }
    if args.get("provider") is not None:
        actor["provider"] = str(args["provider"])
    if args.get("role") is not None:
        actor["role"] = str(args["role"])
    return actor
