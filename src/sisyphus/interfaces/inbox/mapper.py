from __future__ import annotations

from copy import deepcopy

from ...domain.inbox.models import (
    ChangedFile,
    ConversationPayload,
    InboxEvent,
    InboxPayload,
    PullRequestMergedPayload,
)


def changed_file_to_record(changed_file: ChangedFile) -> dict[str, object]:
    record: dict[str, object] = {"path": changed_file.path}
    if changed_file.status is not None:
        record["status"] = changed_file.status
    if changed_file.previous_path is not None:
        record["previous_path"] = changed_file.previous_path
    if changed_file.additions is not None:
        record["additions"] = changed_file.additions
    if changed_file.deletions is not None:
        record["deletions"] = changed_file.deletions
    return record


def conversation_payload_to_record(payload: ConversationPayload) -> dict[str, object]:
    return {
        "title": payload.title,
        "message": payload.message,
        "task_type": payload.task_type,
        "slug": payload.slug,
        "instruction": payload.instruction,
        "agent_id": payload.agent_id,
        "role": payload.role,
        "provider": payload.provider,
        "owned_paths": list(payload.owned_paths),
        "provider_args": list(payload.provider_args),
        "source_context": deepcopy(payload.source_context),
        "adopt_current_changes": payload.adopt_current_changes,
        "adopt_paths": list(payload.adopt_paths),
        "auto_run": payload.auto_run,
    }


def pull_request_merged_payload_to_record(
    payload: PullRequestMergedPayload,
) -> dict[str, object]:
    return {
        "task_id": payload.task_id,
        "branch": payload.branch,
        "repo_full_name": payload.repo_full_name,
        "pr_number": payload.pr_number,
        "title": payload.title,
        "url": payload.url,
        "base_branch": payload.base_branch,
        "head_branch": payload.head_branch,
        "head_sha": payload.head_sha,
        "merge_commit_sha": payload.merge_commit_sha,
        "merged_at": payload.merged_at,
        "merged_by": payload.merged_by,
        "merge_method": payload.merge_method,
        "additions": payload.additions,
        "deletions": payload.deletions,
        "changed_files": [
            changed_file_to_record(changed_file)
            for changed_file in payload.changed_files
        ],
    }


def inbox_payload_to_record(payload: InboxPayload) -> dict[str, object]:
    if isinstance(payload, ConversationPayload):
        return conversation_payload_to_record(payload)
    if isinstance(payload, PullRequestMergedPayload):
        return pull_request_merged_payload_to_record(payload)
    raise TypeError(f"unsupported inbox payload: {type(payload).__name__}")


def inbox_event_to_record(event: InboxEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "status": event.status,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
        "payload": inbox_payload_to_record(event.payload),
        "result": deepcopy(event.result),
        "error": event.error,
    }


__all__ = [
    "changed_file_to_record",
    "conversation_payload_to_record",
    "inbox_event_to_record",
    "inbox_payload_to_record",
    "pull_request_merged_payload_to_record",
]
