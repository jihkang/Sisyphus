from __future__ import annotations

from pathlib import Path
import json
from urllib.parse import urlparse

from .agents import list_agents
from .artifact_resources import is_feature_task_artifact_resource, read_feature_task_artifact_resource
from .api import execute_promotion, get_task, list_tasks, record_merged_pull_request, request_task
from .audit import run_verify
from .bus_jsonl import read_jsonl_events, resolve_event_bus_path
from .closeout import run_close
from .config import load_config
from .conformance import ensure_task_conformance_defaults, summarize_subtask_conformance, summarize_task_conformance
from .daemon import run_daemon
from .evolution.handoff import EvolutionEvidenceSummary, EvolutionVerificationObligation
from .evolution.operator import (
    evaluate_evolution_followup_decision,
    request_evolution_followup,
)
from .evolution.surface import (
    compare_evolution_runs,
    execute_evolution_surface,
    load_evolution_run_artifacts,
    render_evolution_run_compare,
    render_evolution_run_overview,
    render_evolution_run_report,
    render_evolution_run_status,
)
from .planning import (
    approve_task_plan,
    freeze_task_spec,
    generate_subtasks,
    request_plan_changes,
    revise_task_plan,
)
from .metrics import build_value_metrics_report
from .promotion_state import promotion_summary
from .state import load_task_record
from .utils import optional_str, optional_str_list


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

        if tool_name == "sisyphus.list_tasks":
            return {"tasks": list_tasks(repo_root=self.repo_root, config=config)}

        if tool_name == "sisyphus.get_task":
            task_id = str(args["task_id"])
            return {"task": get_task(repo_root=self.repo_root, task_id=task_id, config=config)}

        if tool_name == "sisyphus.evolution_run":
            run_id = str(args["run_id"])
            artifacts = load_evolution_run_artifacts(self.repo_root, run_id)
            return {
                "run_id": run_id,
                "resource_uri": _evolution_run_uri(run_id, "run"),
                "content": render_evolution_run_overview(artifacts),
            }

        if tool_name == "sisyphus.evolution_status":
            run_id = str(args["run_id"])
            artifacts = load_evolution_run_artifacts(self.repo_root, run_id)
            return {
                "run_id": run_id,
                "resource_uri": _evolution_run_uri(run_id, "status"),
                "content": render_evolution_run_status(artifacts),
            }

        if tool_name == "sisyphus.evolution_report":
            run_id = str(args["run_id"])
            artifacts = load_evolution_run_artifacts(self.repo_root, run_id)
            return {
                "run_id": run_id,
                "resource_uri": _evolution_run_uri(run_id, "report"),
                "content": render_evolution_run_report(artifacts),
            }

        if tool_name == "sisyphus.evolution_compare":
            left_run_id = str(args["left_run_id"])
            right_run_id = str(args["right_run_id"])
            left = load_evolution_run_artifacts(self.repo_root, left_run_id)
            right = load_evolution_run_artifacts(self.repo_root, right_run_id)
            comparison = compare_evolution_runs(left, right)
            return {
                "left_run_id": left_run_id,
                "right_run_id": right_run_id,
                "resource_uri": _evolution_compare_uri(left_run_id, right_run_id),
                "content": render_evolution_run_compare(comparison),
            }

        if tool_name == "sisyphus.evolution_execute":
            result = execute_evolution_surface(
                self.repo_root,
                run_id=optional_str(args.get("run_id")),
                target_ids=optional_str_list(args.get("target_ids")),
                task_ids=optional_str_list(args.get("task_ids")),
                max_events=int(args.get("max_events", 50)),
                config=config,
            )
            return {
                "ok": result.ok,
                "run_id": result.run_id,
                "resource_uri": result.resource_uri,
                "artifact_dir": result.artifact_dir,
                "final_stage": result.final_stage,
                "failure_stage": result.failure_stage,
                "content": result.content,
                "error": result.error,
                "error_type": result.error_type,
            }

        if tool_name == "sisyphus.evolution_followup_request":
            result = request_evolution_followup(
                self.repo_root,
                run_id=str(args["run_id"]),
                candidate_id=str(args["candidate_id"]),
                title=str(args["title"]),
                summary=str(args["summary"]),
                requested_task_type=str(args.get("requested_task_type", "feature")),
                slug=optional_str(args.get("slug")),
                target_ids=optional_str_list(args.get("target_ids")),
                owned_paths=optional_str_list(args.get("owned_paths")),
                review_gates=optional_str_list(args.get("review_gates")),
                verification_obligations=_verification_obligations(args.get("verification_obligations")),
                evidence_summary=_evidence_summary(args.get("evidence_summary")),
                config=config,
            )
            return {
                "task_id": result.task_id,
                "task_uri": result.task_uri,
                "run_id": result.run_id,
                "candidate_id": result.candidate_id,
                "requested_targets": list(result.requested_targets),
                "required_review_gates": list(result.required_review_gates),
                "content": result.content,
            }

        if tool_name == "sisyphus.evolution_decide":
            result = evaluate_evolution_followup_decision(
                self.repo_root,
                task_id=str(args["task_id"]),
                claim=optional_str(args.get("claim")),
                config=config,
            )
            return {
                "task_id": result.task_id,
                "task_uri": result.task_uri,
                "run_id": result.run_id,
                "candidate_id": result.candidate_id,
                "gate_status": result.gate_status,
                "envelope_status": result.envelope_status,
                "content": result.content,
            }

        if tool_name == "sisyphus.record_merged_pr":
            result = record_merged_pull_request(
                repo_root=self.repo_root,
                config=config,
                task_id=optional_str(args.get("task_id")),
                branch=optional_str(args.get("branch")),
                repo_full_name=optional_str(args.get("repo_full_name")),
                pr_number=int(args["pr_number"]),
                title=str(args["title"]),
                url=optional_str(args.get("url")),
                base_branch=optional_str(args.get("base_branch")),
                head_branch=optional_str(args.get("head_branch")),
                head_sha=optional_str(args.get("head_sha")),
                merge_commit_sha=optional_str(args.get("merge_commit_sha")),
                merged_at=optional_str(args.get("merged_at")),
                merged_by=optional_str(args.get("merged_by")),
                merge_method=optional_str(args.get("merge_method")),
                additions=int(args["additions"]) if args.get("additions") is not None else None,
                deletions=int(args["deletions"]) if args.get("deletions") is not None else None,
                changed_files=_dict_list(args.get("changed_files")),
            )
            return {
                "ok": result.ok,
                "event_id": result.event_id,
                "event_status": result.event_status,
                "task_id": result.task_id,
                "pr_number": result.pr_number,
                "receipt_path": str(result.receipt_path) if result.receipt_path else None,
                "changeset_path": str(result.changeset_path) if result.changeset_path else None,
                "close_attempted": result.close_attempted,
                "closed": result.closed,
                "close_status": result.close_status,
                "close_gate_codes": result.close_gate_codes,
                "child_retargeted_task_ids": result.child_retargeted_task_ids,
                "error": result.error,
            }

        if tool_name == "sisyphus.execute_promotion":
            result = execute_promotion(
                repo_root=self.repo_root,
                config=config,
                task_id=str(args["task_id"]),
                remote_name=str(args.get("remote_name", "origin")),
                repo_full_name=optional_str(args.get("repo_full_name")),
                title=optional_str(args.get("title")),
                body=optional_str(args.get("body")),
                commit_message=optional_str(args.get("commit_message")),
                base_branch=optional_str(args.get("base_branch")),
                head_branch=optional_str(args.get("head_branch")),
                draft=bool(args.get("draft", True)),
            )
            return {
                "ok": result.ok,
                "task_id": result.task_id,
                "status": result.status,
                "branch": result.branch,
                "base_branch": result.base_branch,
                "head_branch": result.head_branch,
                "commit_sha": result.commit_sha,
                "pr_number": result.pr_number,
                "pr_url": result.pr_url,
                "receipt_path": str(result.receipt_path) if result.receipt_path else None,
                "error": result.error,
            }

        if tool_name == "sisyphus.plan_approve":
            outcome = approve_task_plan(
                repo_root=self.repo_root,
                config=config,
                task_id=str(args["task_id"]),
                reviewer=str(args.get("reviewer", "operator")),
                notes=optional_str(args.get("notes")),
            )
            return {"task_id": outcome.task_id, "plan_status": outcome.plan_status, "task_status": outcome.task_status, "gates": outcome.gates}

        if tool_name == "sisyphus.plan_request_changes":
            outcome = request_plan_changes(
                repo_root=self.repo_root,
                config=config,
                task_id=str(args["task_id"]),
                reviewer=str(args.get("reviewer", "operator")),
                notes=optional_str(args.get("notes")),
            )
            return {"task_id": outcome.task_id, "plan_status": outcome.plan_status, "task_status": outcome.task_status, "gates": outcome.gates}

        if tool_name == "sisyphus.plan_revise":
            outcome = revise_task_plan(
                repo_root=self.repo_root,
                config=config,
                task_id=str(args["task_id"]),
                author=str(args.get("author", "operator")),
                notes=optional_str(args.get("notes")),
            )
            return {"task_id": outcome.task_id, "plan_status": outcome.plan_status, "task_status": outcome.task_status, "gates": outcome.gates}

        if tool_name == "sisyphus.spec_freeze":
            outcome = freeze_task_spec(
                repo_root=self.repo_root,
                config=config,
                task_id=str(args["task_id"]),
                reviewer=str(args.get("reviewer", "operator")),
                notes=optional_str(args.get("notes")),
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
            task_id = optional_str(args.get("task_id"))
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
            return _repo_status_board(tasks, events, build_value_metrics_report(self.repo_root, config))
        if parsed.scheme == "repo" and parsed.netloc == "status" and parsed.path == "/events":
            path = resolve_event_bus_path(self.repo_root, config)
            return {
                "provider": config.event_bus.provider,
                "path": str(path),
                "events": read_jsonl_events(path, limit=50),
            }
        if parsed.scheme == "repo" and parsed.netloc == "status" and parsed.path == "/metrics":
            return build_value_metrics_report(self.repo_root, config)
        if parsed.scheme == "repo" and parsed.netloc == "schema" and parsed.path == "/mcp":
            return _mcp_schema_markdown()
        if parsed.scheme == "evolution":
            return _read_evolution_resource(self.repo_root, parsed)

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
        if resource_name == "promotion":
            doc_path = task_dir / str(task["docs"].get("promotion"))
            if not doc_path.exists():
                return _promotion_resource_placeholder(task)
            return json.loads(doc_path.read_text(encoding="utf-8"))
        if resource_name == "changeset":
            doc_path = task_dir / str(task["docs"].get("changeset"))
            if not doc_path.exists():
                return _changeset_resource_placeholder(task)
            return doc_path.read_text(encoding="utf-8")
        if resource_name == "agents":
            return {
                "agents": list_agents(
                    repo_root=self.repo_root,
                    config=config,
                    task_id=task_id,
                )
            }
        if is_feature_task_artifact_resource(resource_name):
            if task.get("type") != "feature":
                return _artifact_resource_unavailable(
                    task,
                    resource_name=resource_name,
                    reason="resource is only available for feature tasks",
                )
            try:
                return read_feature_task_artifact_resource(task, task_dir, resource_name)
            except Exception as exc:
                return _artifact_resource_unavailable(
                    task,
                    resource_name=resource_name,
                    reason=str(exc) or "artifact projection is not available for the current task state",
                )

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
            "name": "sisyphus.evolution_execute",
            "description": "Start a new read-only evolution run and return reviewable run metadata.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "target_ids": {"type": "array", "items": {"type": "string"}},
                    "task_ids": {"type": "array", "items": {"type": "string"}},
                    "max_events": {"type": "integer"},
                },
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "run_id": {"type": ["string", "null"]},
                    "resource_uri": {"type": ["string", "null"]},
                    "artifact_dir": {"type": ["string", "null"]},
                    "final_stage": {"type": ["string", "null"]},
                    "failure_stage": {"type": ["string", "null"]},
                    "content": {"type": "string"},
                    "error": {"type": ["string", "null"]},
                    "error_type": {"type": ["string", "null"]},
                },
            },
        },
        {
            "name": "sisyphus.evolution_followup_request",
            "description": "Create a review-gated Sisyphus follow-up task from an evolution run.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "candidate_id": {"type": "string"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "requested_task_type": {"type": "string", "enum": ["feature", "issue"]},
                    "slug": {"type": "string"},
                    "target_ids": {"type": "array", "items": {"type": "string"}},
                    "owned_paths": {"type": "array", "items": {"type": "string"}},
                    "review_gates": {"type": "array", "items": {"type": "string"}},
                    "verification_obligations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "claim": {"type": "string"},
                                "method": {"type": "string"},
                                "required": {"type": "boolean"},
                            },
                            "required": ["claim", "method"],
                            "additionalProperties": False,
                        },
                    },
                    "evidence_summary": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "kind": {"type": "string"},
                                "summary": {"type": "string"},
                                "locator": {"type": "string"},
                            },
                            "required": ["kind", "summary"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["run_id", "candidate_id", "title", "summary"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "task_uri": {"type": "string"},
                    "run_id": {"type": "string"},
                    "candidate_id": {"type": "string"},
                    "requested_targets": {"type": "array", "items": {"type": "string"}},
                    "required_review_gates": {"type": "array", "items": {"type": "string"}},
                    "content": {"type": "string"},
                },
            },
        },
        {
            "name": "sisyphus.evolution_decide",
            "description": "Evaluate an evolution follow-up task and record the current promotion or invalidation decision.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "claim": {"type": "string"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "task_uri": {"type": "string"},
                    "run_id": {"type": "string"},
                    "candidate_id": {"type": "string"},
                    "gate_status": {"type": "string"},
                    "envelope_status": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
        },
        {
            "name": "sisyphus.evolution_run",
            "description": "Render the read-only overview for a persisted evolution run.",
            "inputSchema": {
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "resource_uri": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
        },
        {
            "name": "sisyphus.evolution_status",
            "description": "Render the read-only status summary for a persisted evolution run.",
            "inputSchema": {
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "resource_uri": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
        },
        {
            "name": "sisyphus.evolution_report",
            "description": "Render the read-only report for a persisted evolution run.",
            "inputSchema": {
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "resource_uri": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
        },
        {
            "name": "sisyphus.evolution_compare",
            "description": "Render a read-only comparison across two persisted evolution runs.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "left_run_id": {"type": "string"},
                    "right_run_id": {"type": "string"},
                },
                "required": ["left_run_id", "right_run_id"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "left_run_id": {"type": "string"},
                    "right_run_id": {"type": "string"},
                    "resource_uri": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
        },
        {
            "name": "sisyphus.record_merged_pr",
            "description": "Record a merged pull request as a promotion receipt and project a changeset summary.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "branch": {"type": "string"},
                    "repo_full_name": {"type": "string"},
                    "pr_number": {"type": "integer", "minimum": 1},
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "base_branch": {"type": "string"},
                    "head_branch": {"type": "string"},
                    "head_sha": {"type": "string"},
                    "merge_commit_sha": {"type": "string"},
                    "merged_at": {"type": "string"},
                    "merged_by": {"type": "string"},
                    "merge_method": {"type": "string"},
                    "additions": {"type": "integer"},
                    "deletions": {"type": "integer"},
                    "changed_files": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["pr_number", "title"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "event_id": {"type": ["string", "null"]},
                    "event_status": {"type": "string"},
                    "task_id": {"type": ["string", "null"]},
                    "pr_number": {"type": ["integer", "null"]},
                    "receipt_path": {"type": ["string", "null"]},
                    "changeset_path": {"type": ["string", "null"]},
                    "close_attempted": {"type": "boolean"},
                    "closed": {"type": "boolean"},
                    "close_status": {"type": ["string", "null"]},
                    "close_gate_codes": {"type": "array", "items": {"type": "string"}},
                    "child_retargeted_task_ids": {"type": "array", "items": {"type": "string"}},
                    "error": {"type": ["string", "null"]},
                },
            },
        },
        {
            "name": "sisyphus.execute_promotion",
            "description": "Commit, push, and open a pull request for a promotable task branch.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "remote_name": {"type": "string"},
                    "repo_full_name": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "commit_message": {"type": "string"},
                    "base_branch": {"type": "string"},
                    "head_branch": {"type": "string"},
                    "draft": {"type": "boolean"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "task_id": {"type": ["string", "null"]},
                    "status": {"type": ["string", "null"]},
                    "branch": {"type": ["string", "null"]},
                    "base_branch": {"type": ["string", "null"]},
                    "head_branch": {"type": ["string", "null"]},
                    "commit_sha": {"type": ["string", "null"]},
                    "pr_number": {"type": ["integer", "null"]},
                    "pr_url": {"type": ["string", "null"]},
                    "receipt_path": {"type": ["string", "null"]},
                    "error": {"type": ["string", "null"]},
                },
            },
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
        {"uri": "repo://status/metrics", "description": "Repository-level workflow value metrics derived from task state and lifecycle events."},
        {"uri": "repo://schema/mcp", "description": "Human-readable MCP tool and resource schema for Sisyphus."},
        {"uri": "evolution://<run-id>/run", "description": "Read-only overview for a persisted evolution run."},
        {"uri": "evolution://<run-id>/status", "description": "Read-only status summary for a persisted evolution run."},
        {"uri": "evolution://<run-id>/report", "description": "Read-only report for a persisted evolution run."},
        {"uri": "evolution://compare/<left-run-id>/<right-run-id>", "description": "Read-only comparison across two persisted evolution runs."},
        {"uri": "task://<task-id>/record", "description": "Raw task record JSON."},
        {"uri": "task://<task-id>/conformance", "description": "Task-level conformance summary."},
        {"uri": "task://<task-id>/timeline", "description": "Task and subtask conformance/drift timeline."},
        {"uri": "task://<task-id>/brief", "description": "Task brief markdown."},
        {"uri": "task://<task-id>/plan", "description": "Task plan markdown."},
        {"uri": "task://<task-id>/repro", "description": "Task repro markdown for issue tasks."},
        {"uri": "task://<task-id>/verify", "description": "Task verification markdown."},
        {"uri": "task://<task-id>/log", "description": "Task log markdown."},
        {"uri": "task://<task-id>/promotion", "description": "Recorded promotion receipt JSON for a merged pull request."},
        {"uri": "task://<task-id>/changeset", "description": "Human-readable merged pull request changeset markdown."},
        {"uri": "task://<task-id>/agents", "description": "Tracked agent records for a task."},
        {"uri": "task://<task-id>/artifact-graph", "description": "Read-only FeatureChangeArtifact graph projection for a feature task."},
        {"uri": "task://<task-id>/slot-bindings", "description": "Projected slot bindings for a feature task artifact envelope."},
        {"uri": "task://<task-id>/verification-claims", "description": "Projected verification claims bound to a feature task artifact envelope."},
        {"uri": "task://<task-id>/promotion-summary", "description": "Read-only promotion decision summary derived from the feature task artifact projection."},
        {"uri": "task://<task-id>/invalidation-summary", "description": "Read-only invalidation summary derived from the feature task artifact projection."},
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

def _dict_list(value: object) -> list[dict[str, object]] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise TypeError(f"expected list value, got: {type(value).__name__}")
    normalized: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise TypeError("expected changed_files entries to be objects")
        normalized.append({str(key): item[key] for key in item})
    return normalized


def _verification_obligations(
    value: object,
) -> tuple[EvolutionVerificationObligation, ...] | None:
    raw_items = _dict_list(value)
    if raw_items is None:
        return None
    normalized: list[EvolutionVerificationObligation] = []
    for index, item in enumerate(raw_items, start=1):
        claim = str(item.get("claim", "")).strip()
        method = str(item.get("method", "")).strip()
        if not claim or not method:
            raise ValueError(
                f"verification_obligations[{index}] requires non-empty claim and method"
            )
        normalized.append(
            EvolutionVerificationObligation(
                claim=claim,
                method=method,
                required=bool(item.get("required", True)),
            )
        )
    return tuple(normalized)


def _evidence_summary(value: object) -> tuple[EvolutionEvidenceSummary, ...] | None:
    raw_items = _dict_list(value)
    if raw_items is None:
        return None
    normalized: list[EvolutionEvidenceSummary] = []
    for index, item in enumerate(raw_items, start=1):
        kind = str(item.get("kind", "")).strip()
        summary = str(item.get("summary", "")).strip()
        if not kind or not summary:
            raise ValueError(
                f"evidence_summary[{index}] requires non-empty kind and summary"
            )
        normalized.append(
            EvolutionEvidenceSummary(
                kind=kind,
                summary=summary,
                locator=optional_str(item.get("locator")),
            )
        )
    return tuple(normalized)


def _evolution_run_uri(run_id: str, view: str) -> str:
    return f"evolution://{run_id}/{view}"


def _evolution_compare_uri(left_run_id: str, right_run_id: str) -> str:
    return f"evolution://compare/{left_run_id}/{right_run_id}"


def _read_evolution_resource(repo_root: Path, parsed) -> str:
    if parsed.netloc == "compare":
        left_run_id, right_run_id = _parse_compare_path(parsed.path)
        left = load_evolution_run_artifacts(repo_root, left_run_id)
        right = load_evolution_run_artifacts(repo_root, right_run_id)
        comparison = compare_evolution_runs(left, right)
        return render_evolution_run_compare(comparison)

    run_id = parsed.netloc
    resource_name = parsed.path.lstrip("/")
    if not run_id:
        raise ValueError("evolution resource must include a run id")
    artifacts = load_evolution_run_artifacts(repo_root, run_id)
    if resource_name == "run":
        return render_evolution_run_overview(artifacts)
    if resource_name == "status":
        return render_evolution_run_status(artifacts)
    if resource_name == "report":
        return render_evolution_run_report(artifacts)
    raise ValueError(f"unsupported evolution resource `{resource_name}`")


def _parse_compare_path(path: str) -> tuple[str, str]:
    parts = [part for part in path.split("/") if part]
    if len(parts) != 2:
        raise ValueError("evolution compare resource must include left and right run ids")
    return parts[0], parts[1]


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


def _promotion_resource_placeholder(task: dict) -> dict[str, object]:
    return {
        "task_id": task.get("id"),
        "status": "not_recorded",
        "promotion": promotion_summary(task),
    }


def _changeset_resource_placeholder(task: dict) -> str:
    return "\n".join(
        [
            "# Changeset",
            "",
            f"- Task: `{task.get('id')}`",
            "- Status: `not_recorded`",
            "- Notes: no merged pull request receipt has been recorded for this task yet",
            "",
        ]
    )


def _artifact_resource_unavailable(task: dict, *, resource_name: str, reason: str) -> dict[str, object]:
    return {
        "task_id": task.get("id"),
        "task_type": task.get("type"),
        "resource": resource_name,
        "status": "unavailable",
        "reason": reason,
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
