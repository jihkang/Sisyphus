from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import cast


MAX_EVENT_ID_LENGTH = 128
MAX_TITLE_LENGTH = 512
MAX_MESSAGE_LENGTH = 100_000
MAX_SHORT_STRING_LENGTH = 4_096
MAX_PATH_LENGTH = 1_024
MAX_LIST_ITEMS = 1_000
MAX_SOURCE_CONTEXT_DEPTH = 8
MAX_SOURCE_CONTEXT_NODES = 4_096
MAX_SOURCE_CONTEXT_STRING_LENGTH = 16_384

_EVENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
_WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:")


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

    @classmethod
    def from_dict(cls, raw: object, *, field: str) -> ChangedFile:
        data = _mapping(raw, field)
        _check_fields(
            data,
            allowed={"path", "status", "previous_path", "additions", "deletions"},
            required={"path"},
            field=field,
        )
        status = _optional_string(data, "status", field=field, max_length=64)
        if status is not None and status not in {
            "added",
            "changed",
            "copied",
            "modified",
            "removed",
            "renamed",
            "unchanged",
        }:
            raise InboxValidationError("invalid_value", f"{field}.status", f"unsupported status: {status}")
        return cls(
            path=_relative_path(data["path"], f"{field}.path"),
            status=status,
            previous_path=(
                _relative_path(data["previous_path"], f"{field}.previous_path")
                if "previous_path" in data
                else None
            ),
            additions=_optional_non_negative_int(data, "additions", field=field),
            deletions=_optional_non_negative_int(data, "deletions", field=field),
        )

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"path": self.path}
        if self.status is not None:
            result["status"] = self.status
        if self.previous_path is not None:
            result["previous_path"] = self.previous_path
        if self.additions is not None:
            result["additions"] = self.additions
        if self.deletions is not None:
            result["deletions"] = self.deletions
        return result


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

    @classmethod
    def from_dict(cls, raw: object, *, field: str = "payload") -> ConversationPayload:
        data = _mapping(raw, field)
        _check_fields(
            data,
            allowed={
                "title",
                "message",
                "task_type",
                "slug",
                "instruction",
                "agent_id",
                "role",
                "provider",
                "owned_paths",
                "provider_args",
                "source_context",
                "adopt_current_changes",
                "adopt_paths",
                "auto_run",
            },
            required={"message"},
            field=field,
        )
        task_type = _string(data.get("task_type", "feature"), f"{field}.task_type", max_length=16)
        if task_type not in {"feature", "issue"}:
            raise InboxValidationError("invalid_value", f"{field}.task_type", f"unsupported task type: {task_type}")
        return cls(
            title=_string(data.get("title", ""), f"{field}.title", max_length=MAX_TITLE_LENGTH),
            message=_string(
                data["message"],
                f"{field}.message",
                max_length=MAX_MESSAGE_LENGTH,
                allow_empty=False,
            ),
            task_type=task_type,
            slug=_string(data.get("slug", ""), f"{field}.slug", max_length=128),
            instruction=_nullable_string(
                data.get("instruction"),
                f"{field}.instruction",
                max_length=MAX_MESSAGE_LENGTH,
                strip=False,
            ),
            agent_id=_string(data.get("agent_id", "worker-1"), f"{field}.agent_id", max_length=256),
            role=_string(data.get("role", "worker"), f"{field}.role", max_length=256),
            provider=_string(data.get("provider", "codex"), f"{field}.provider", max_length=256),
            owned_paths=_path_list(data.get("owned_paths", []), f"{field}.owned_paths"),
            provider_args=_string_list(
                data.get("provider_args", []),
                f"{field}.provider_args",
                max_item_length=MAX_SHORT_STRING_LENGTH,
            ),
            source_context=_source_context(data.get("source_context", {}), f"{field}.source_context"),
            adopt_current_changes=_boolean(
                data.get("adopt_current_changes", False),
                f"{field}.adopt_current_changes",
            ),
            adopt_paths=_path_list(data.get("adopt_paths", []), f"{field}.adopt_paths"),
            auto_run=_boolean(data.get("auto_run", True), f"{field}.auto_run"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "message": self.message,
            "task_type": self.task_type,
            "slug": self.slug,
            "instruction": self.instruction,
            "agent_id": self.agent_id,
            "role": self.role,
            "provider": self.provider,
            "owned_paths": list(self.owned_paths),
            "provider_args": list(self.provider_args),
            "source_context": _clone_json_object(self.source_context),
            "adopt_current_changes": self.adopt_current_changes,
            "adopt_paths": list(self.adopt_paths),
            "auto_run": self.auto_run,
        }


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

    @classmethod
    def from_dict(cls, raw: object, *, field: str = "payload") -> PullRequestMergedPayload:
        data = _mapping(raw, field)
        _check_fields(
            data,
            allowed={
                "task_id",
                "branch",
                "repo_full_name",
                "pr_number",
                "title",
                "url",
                "base_branch",
                "head_branch",
                "head_sha",
                "merge_commit_sha",
                "merged_at",
                "merged_by",
                "merge_method",
                "additions",
                "deletions",
                "changed_files",
            },
            required={"pr_number", "title"},
            field=field,
        )
        task_id = _optional_string(data, "task_id", field=field, max_length=256)
        branch = _optional_string(data, "branch", field=field, max_length=MAX_SHORT_STRING_LENGTH)
        head_branch = _optional_string(data, "head_branch", field=field, max_length=MAX_SHORT_STRING_LENGTH)
        if branch is None:
            branch = head_branch
        if task_id is None and branch is None:
            raise InboxValidationError(
                "missing_field",
                field,
                "pull request merge event requires task_id or branch/head_branch",
            )
        pr_number = _integer(data["pr_number"], f"{field}.pr_number")
        if pr_number < 1:
            raise InboxValidationError("invalid_value", f"{field}.pr_number", "must be positive")
        merge_method = _optional_string(data, "merge_method", field=field, max_length=32)
        if merge_method is not None and merge_method not in {"merge", "rebase", "squash"}:
            raise InboxValidationError(
                "invalid_value",
                f"{field}.merge_method",
                f"unsupported merge method: {merge_method}",
            )
        changed_files_raw = data.get("changed_files", [])
        changed_files_data = _list(changed_files_raw, f"{field}.changed_files")
        return cls(
            task_id=task_id,
            branch=branch,
            repo_full_name=_optional_string(data, "repo_full_name", field=field, max_length=512),
            pr_number=pr_number,
            title=_string(
                data["title"],
                f"{field}.title",
                max_length=MAX_TITLE_LENGTH,
                allow_empty=False,
            ),
            url=_optional_string(data, "url", field=field, max_length=MAX_SHORT_STRING_LENGTH),
            base_branch=_optional_string(data, "base_branch", field=field, max_length=MAX_SHORT_STRING_LENGTH),
            head_branch=head_branch,
            head_sha=_optional_string(data, "head_sha", field=field, max_length=256),
            merge_commit_sha=_optional_string(data, "merge_commit_sha", field=field, max_length=256),
            merged_at=_optional_string(data, "merged_at", field=field, max_length=128),
            merged_by=_optional_string(data, "merged_by", field=field, max_length=256),
            merge_method=merge_method,
            additions=_optional_non_negative_int(data, "additions", field=field),
            deletions=_optional_non_negative_int(data, "deletions", field=field),
            changed_files=tuple(
                ChangedFile.from_dict(item, field=f"{field}.changed_files[{index}]")
                for index, item in enumerate(changed_files_data)
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "branch": self.branch,
            "repo_full_name": self.repo_full_name,
            "pr_number": self.pr_number,
            "title": self.title,
            "url": self.url,
            "base_branch": self.base_branch,
            "head_branch": self.head_branch,
            "head_sha": self.head_sha,
            "merge_commit_sha": self.merge_commit_sha,
            "merged_at": self.merged_at,
            "merged_by": self.merged_by,
            "merge_method": self.merge_method,
            "additions": self.additions,
            "deletions": self.deletions,
            "changed_files": [item.to_dict() for item in self.changed_files],
        }


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

    @classmethod
    def from_dict(cls, raw: object) -> InboxEvent:
        data = _mapping(raw, "event")
        _check_fields(
            data,
            allowed={"id", "event_type", "status", "created_at", "updated_at", "payload", "result", "error"},
            required={"id", "event_type", "status", "created_at", "updated_at", "payload", "result", "error"},
            field="event",
        )
        event_id = _string(data["id"], "event.id", max_length=MAX_EVENT_ID_LENGTH, allow_empty=False)
        if _EVENT_ID_PATTERN.fullmatch(event_id) is None:
            raise InboxValidationError(
                "invalid_value",
                "event.id",
                "must contain only letters, digits, dot, underscore, or hyphen",
            )
        event_type = _string(data["event_type"], "event.event_type", max_length=64, allow_empty=False)
        if event_type == "conversation":
            payload: InboxPayload = ConversationPayload.from_dict(data["payload"])
        elif event_type == "pull_request_merged":
            payload = PullRequestMergedPayload.from_dict(data["payload"])
        else:
            raise InboxValidationError(
                "unsupported_event_type",
                "event.event_type",
                f"unsupported event type: {event_type}",
            )
        status = _string(data["status"], "event.status", max_length=32, allow_empty=False)
        if status not in {"processing", "queued"}:
            raise InboxValidationError(
                "invalid_value",
                "event.status",
                "must be queued or processing",
            )
        result = _nullable_json_object(data["result"], "event.result")
        error = _nullable_string(data["error"], "event.error", max_length=MAX_SHORT_STRING_LENGTH, strip=False)
        return cls(
            id=event_id,
            event_type=event_type,
            status=status,
            created_at=_string(data["created_at"], "event.created_at", max_length=128, allow_empty=False),
            updated_at=_string(data["updated_at"], "event.updated_at", max_length=128, allow_empty=False),
            payload=payload,
            result=result,
            error=error,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "payload": self.payload.to_dict(),
            "result": _clone_json_object(self.result) if self.result is not None else None,
            "error": self.error,
        }


def _mapping(raw: object, field: str) -> dict[str, object]:
    if type(raw) is not dict:
        raise InboxValidationError("invalid_type", field, "must be an object")
    data = cast(dict[object, object], raw)
    if any(type(key) is not str for key in data):
        raise InboxValidationError("invalid_type", field, "object keys must be strings")
    if len(data) > MAX_LIST_ITEMS:
        raise InboxValidationError("value_too_large", field, f"must contain at most {MAX_LIST_ITEMS} keys")
    return cast(dict[str, object], data)


def _check_fields(
    data: dict[str, object],
    *,
    allowed: set[str],
    required: set[str],
    field: str,
) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise InboxValidationError("unknown_field", field, f"unknown fields: {', '.join(unknown)}")
    missing = sorted(required - set(data))
    if missing:
        raise InboxValidationError("missing_field", field, f"missing fields: {', '.join(missing)}")


def _string(
    value: object,
    field: str,
    *,
    max_length: int,
    allow_empty: bool = True,
    strip: bool = True,
) -> str:
    if type(value) is not str:
        raise InboxValidationError("invalid_type", field, "must be a string")
    result = cast(str, value).strip() if strip else cast(str, value)
    if not allow_empty and not result:
        raise InboxValidationError("invalid_value", field, "must not be empty")
    if len(result) > max_length:
        raise InboxValidationError("value_too_large", field, f"must be at most {max_length} characters")
    return result


def _nullable_string(
    value: object,
    field: str,
    *,
    max_length: int,
    strip: bool = True,
) -> str | None:
    if value is None:
        return None
    return _string(value, field, max_length=max_length, allow_empty=True, strip=strip)


def _optional_string(
    data: dict[str, object],
    key: str,
    *,
    field: str,
    max_length: int,
) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    result = _string(value, f"{field}.{key}", max_length=max_length)
    return result or None


def _boolean(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise InboxValidationError("invalid_type", field, "must be a boolean")
    return cast(bool, value)


def _integer(value: object, field: str) -> int:
    if type(value) is not int:
        raise InboxValidationError("invalid_type", field, "must be an integer")
    return cast(int, value)


def _optional_non_negative_int(data: dict[str, object], key: str, *, field: str) -> int | None:
    if key not in data or data[key] is None:
        return None
    result = _integer(data[key], f"{field}.{key}")
    if result < 0:
        raise InboxValidationError("invalid_value", f"{field}.{key}", "must be non-negative")
    return result


def _list(value: object, field: str) -> list[object]:
    if type(value) is not list:
        raise InboxValidationError("invalid_type", field, "must be an array")
    result = cast(list[object], value)
    if len(result) > MAX_LIST_ITEMS:
        raise InboxValidationError("value_too_large", field, f"must contain at most {MAX_LIST_ITEMS} items")
    return result


def _string_list(value: object, field: str, *, max_item_length: int) -> tuple[str, ...]:
    return tuple(
        _string(item, f"{field}[{index}]", max_length=max_item_length, strip=False)
        for index, item in enumerate(_list(value, field))
    )


def _path_list(value: object, field: str) -> tuple[str, ...]:
    return tuple(_relative_path(item, f"{field}[{index}]") for index, item in enumerate(_list(value, field)))


def _relative_path(value: object, field: str) -> str:
    path = _string(value, field, max_length=MAX_PATH_LENGTH, allow_empty=False).replace("\\", "/")
    if path.startswith("/") or _WINDOWS_DRIVE_PATTERN.match(path):
        raise InboxValidationError("unsafe_path", field, "must be repository-relative")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise InboxValidationError("unsafe_path", field, "must not contain empty, dot, or parent segments")
    if any(any(ord(character) < 32 for character in part) for part in parts):
        raise InboxValidationError("unsafe_path", field, "must not contain control characters")
    return path


def _source_context(value: object, field: str) -> dict[str, object]:
    if type(value) is not dict:
        raise InboxValidationError("invalid_type", field, "must be an object")
    budget = [0]
    cloned = _json_value(value, field, depth=0, budget=budget)
    return cast(dict[str, object], cloned)


def _nullable_json_object(value: object, field: str) -> dict[str, object] | None:
    if value is None:
        return None
    return _source_context(value, field)


def _json_value(value: object, field: str, *, depth: int, budget: list[int]) -> object:
    budget[0] += 1
    if budget[0] > MAX_SOURCE_CONTEXT_NODES:
        raise InboxValidationError(
            "value_too_large",
            field,
            f"must contain at most {MAX_SOURCE_CONTEXT_NODES} values",
        )
    if depth > MAX_SOURCE_CONTEXT_DEPTH:
        raise InboxValidationError(
            "value_too_large",
            field,
            f"must be at most {MAX_SOURCE_CONTEXT_DEPTH} levels deep",
        )
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        integer = cast(int, value)
        if abs(integer) > 2**63 - 1:
            raise InboxValidationError("value_too_large", field, "integer is outside signed 64-bit range")
        return integer
    if type(value) is float:
        number = cast(float, value)
        if not math.isfinite(number):
            raise InboxValidationError("invalid_value", field, "floating-point values must be finite")
        return number
    if type(value) is str:
        return _string(
            value,
            field,
            max_length=MAX_SOURCE_CONTEXT_STRING_LENGTH,
            strip=False,
        )
    if type(value) is list:
        return [
            _json_value(item, f"{field}[{index}]", depth=depth + 1, budget=budget)
            for index, item in enumerate(_list(value, field))
        ]
    if type(value) is dict:
        data = _mapping(value, field)
        result: dict[str, object] = {}
        for key, item in data.items():
            _string(key, f"{field}.<key>", max_length=256, allow_empty=False, strip=False)
            result[key] = _json_value(item, f"{field}.{key}", depth=depth + 1, budget=budget)
        return result
    raise InboxValidationError("invalid_type", field, "must contain only JSON-compatible values")


def _clone_json_object(value: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], _json_value(value, "value", depth=0, budget=[0]))


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
