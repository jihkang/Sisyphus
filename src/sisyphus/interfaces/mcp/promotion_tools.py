from __future__ import annotations

from types import MappingProxyType
from pathlib import Path

from ...api import execute_promotion, record_merged_pull_request
from ...config import SisyphusConfig
from ...shared.coerce import optional_str
from .coercion import dict_list


def _record_merged_pr(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    record_merged_pr=record_merged_pull_request,
    **_: object,
) -> dict[str, object]:
    result = record_merged_pr(
        repo_root=repo_root,
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
        changed_files=dict_list(args.get("changed_files")),
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


def _execute_promotion(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    execute_promotion_fn=execute_promotion,
    **_: object,
) -> dict[str, object]:
    result = execute_promotion_fn(
        repo_root=repo_root,
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


TOOL_EXECUTORS = MappingProxyType(
    {
        "sisyphus.record_merged_pr": _record_merged_pr,
        "sisyphus.execute_promotion": _execute_promotion,
    }
)


def call_promotion_tool(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    tool_name: str,
    args: dict[str, object],
    record_merged_pr=record_merged_pull_request,
    execute_promotion_fn=execute_promotion,
) -> dict[str, object] | None:
    executor = TOOL_EXECUTORS.get(tool_name)
    if executor is None:
        return None
    return executor(
        repo_root=repo_root,
        config=config,
        args=args,
        record_merged_pr=record_merged_pr,
        execute_promotion_fn=execute_promotion_fn,
    )


__all__ = ["TOOL_EXECUTORS", "call_promotion_tool"]
