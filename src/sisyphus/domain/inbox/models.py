from __future__ import annotations

from dataclasses import dataclass


MAX_EVENT_ID_LENGTH = 128
MAX_TITLE_LENGTH = 512
MAX_MESSAGE_LENGTH = 100_000
MAX_SHORT_STRING_LENGTH = 4_096
MAX_PATH_LENGTH = 1_024
MAX_LIST_ITEMS = 1_000
MAX_SOURCE_CONTEXT_DEPTH = 8
MAX_SOURCE_CONTEXT_NODES = 4_096
MAX_SOURCE_CONTEXT_STRING_LENGTH = 16_384


class InboxValidationError(ValueError):
    """Raised when an inbox event does not match the persisted contract."""

    def __init__(self, code: str, field: str, message: str) -> None:
        self.code = code
        self.field = field
        self.detail = message
        super().__init__(f"{field}: {message}")


@dataclass(frozen=True, slots=True)
class ChangedFile:
    path: str
    status: str | None = None
    previous_path: str | None = None
    additions: int | None = None
    deletions: int | None = None


@dataclass(frozen=True, slots=True)
class ConversationPayload:
    title: str
    message: str
    task_type: str
    slug: str
    instruction: str | None
    agent_id: str
    role: str
    provider: str
    owned_paths: tuple[str, ...]
    provider_args: tuple[str, ...]
    source_context: dict[str, object]
    adopt_current_changes: bool
    adopt_paths: tuple[str, ...]
    auto_run: bool


@dataclass(frozen=True, slots=True)
class PullRequestMergedPayload:
    task_id: str | None
    branch: str | None
    repo_full_name: str | None
    pr_number: int
    title: str
    url: str | None
    base_branch: str | None
    head_branch: str | None
    head_sha: str | None
    merge_commit_sha: str | None
    merged_at: str | None
    merged_by: str | None
    merge_method: str | None
    additions: int | None
    deletions: int | None
    changed_files: tuple[ChangedFile, ...]


InboxPayload = ConversationPayload | PullRequestMergedPayload


@dataclass(frozen=True, slots=True)
class InboxEvent:
    id: str
    event_type: str
    status: str
    created_at: str
    updated_at: str
    payload: InboxPayload
    result: dict[str, object] | None
    error: str | None


__all__ = [
    "ChangedFile",
    "ConversationPayload",
    "InboxEvent",
    "InboxPayload",
    "InboxValidationError",
    "MAX_EVENT_ID_LENGTH",
    "MAX_LIST_ITEMS",
    "MAX_MESSAGE_LENGTH",
    "MAX_PATH_LENGTH",
    "MAX_SHORT_STRING_LENGTH",
    "MAX_SOURCE_CONTEXT_DEPTH",
    "MAX_SOURCE_CONTEXT_NODES",
    "MAX_SOURCE_CONTEXT_STRING_LENGTH",
    "MAX_TITLE_LENGTH",
    "PullRequestMergedPayload",
]
