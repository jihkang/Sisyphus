from __future__ import annotations

import json
from pathlib import Path
import sys

from ....api import queue_conversation, request_task
from ....api import queue_pull_request_merged as queue_pull_request_merged_api
from ..parsing import parse_changed_file_json


def handle_ingest_conversation(
    *,
    repo_root: Path,
    message: str,
    title: str | None,
    task_type: str,
    slug: str | None,
    instruction: str | None,
    agent_id: str,
    role: str,
    provider: str,
    owned_paths: list[str] | None,
    provider_args: list[str] | None,
    adopt_current_changes: bool,
    adopt_paths: list[str] | None,
    no_run: bool,
) -> int:
    try:
        queued = queue_conversation(
            repo_root=repo_root,
            message=message,
            title=title,
            task_type=task_type,
            slug=slug,
            instruction=instruction,
            agent_id=agent_id,
            role=role,
            provider=provider,
            owned_paths=owned_paths,
            provider_args=provider_args,
            adopt_current_changes=adopt_current_changes,
            adopt_paths=adopt_paths,
            auto_run=not no_run,
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"queued {queued.event_id}")
    print(f"event_file: {queued.event_path}")
    print(f"task_type: {queued.event['payload']['task_type']}")
    print(f"slug: {queued.event['payload']['slug']}")
    return 0


def handle_ingest_pull_request_merged(
    *,
    repo_root: Path,
    task_id: str | None,
    branch: str | None,
    repo_full_name: str | None,
    pr_number: int,
    title: str,
    url: str | None,
    base_branch: str | None,
    head_branch: str | None,
    head_sha: str | None,
    merge_commit_sha: str | None,
    merged_at: str | None,
    merged_by: str | None,
    merge_method: str | None,
    additions: int | None,
    deletions: int | None,
    changed_file_json: list[str] | None,
) -> int:
    try:
        queued = queue_pull_request_merged_api(
            repo_root=repo_root,
            task_id=task_id,
            branch=branch,
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            title=title,
            url=url,
            base_branch=base_branch,
            head_branch=head_branch,
            head_sha=head_sha,
            merge_commit_sha=merge_commit_sha,
            merged_at=merged_at,
            merged_by=merged_by,
            merge_method=merge_method,
            additions=additions,
            deletions=deletions,
            changed_files=parse_changed_file_json(changed_file_json),
        )
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"queued {queued.event_id}")
    print(f"event_file: {queued.event_path}")
    print(f"pr_number: {queued.event['payload']['pr_number']}")
    if queued.event["payload"].get("task_id"):
        print(f"task_id: {queued.event['payload']['task_id']}")
    if queued.event["payload"].get("branch"):
        print(f"branch: {queued.event['payload']['branch']}")
    return 0


def handle_request(
    *,
    repo_root: Path,
    message: str,
    title: str | None,
    task_type: str,
    slug: str | None,
    instruction: str | None,
    agent_id: str,
    role: str,
    provider: str,
    owned_paths: list[str] | None,
    provider_args: list[str] | None,
    adopt_current_changes: bool,
    adopt_paths: list[str] | None,
    no_run: bool,
) -> int:
    result = request_task(
        repo_root=repo_root,
        message=message,
        title=title,
        task_type=task_type,
        slug=slug,
        instruction=instruction,
        agent_id=agent_id,
        role=role,
        provider=provider,
        owned_paths=owned_paths,
        provider_args=provider_args,
        adopt_current_changes=adopt_current_changes,
        adopt_paths=adopt_paths,
        auto_run=not no_run,
    )
    if not result.ok:
        print(f"error: {result.error or 'request processing failed'}", file=sys.stderr)
        return 1

    if not result.task_id or not result.task:
        print(f"error: request completed without task id for event {result.event_id}", file=sys.stderr)
        return 1
    task = result.task

    print(f"request {result.event_id}")
    print(f"task_id: {task['id']}")
    print(f"slug: {task.get('slug')}")
    requested_slug = task.get("meta", {}).get("requested_slug")
    if requested_slug and requested_slug != task.get("slug"):
        print(f"requested_slug: {requested_slug}")
    followup_of_task_id = task.get("meta", {}).get("followup_of_task_id")
    if followup_of_task_id:
        print(f"followup_of_task_id: {followup_of_task_id}")
    print(f"status: {task.get('status')}")
    print(f"plan_status: {task.get('plan_status')}")
    print(f"spec_status: {task.get('spec_status')}")
    print(f"workflow_phase: {task.get('workflow_phase')}")
    adopted = task.get("meta", {}).get("adopted_changes")
    if isinstance(adopted, dict) and adopted.get("paths"):
        print(f"adopted_paths: {len(adopted['paths'])}")
        if adopted.get("source_branch"):
            print(f"adopted_from_branch: {adopted['source_branch']}")
    print(f"orchestrated: {result.orchestrated}")
    return 0


__all__ = [
    "handle_ingest_conversation",
    "handle_ingest_pull_request_merged",
    "handle_request",
]
