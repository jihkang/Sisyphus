from __future__ import annotations

from ...domain.agent.models import Agent
from .record_mapper import DataclassRecordMapper, FieldMapping


def _decode_string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
        raise ValueError("expected a JSON array of strings")
    return tuple(value)


def _encode_string_tuple(value: object) -> list[str]:
    if not isinstance(value, tuple) or any(not isinstance(item, str) for item in value):
        raise ValueError("expected a tuple of strings")
    return list(value)


AGENT_RECORD_MAPPER = DataclassRecordMapper(
    Agent,
    {
        "agent_id": FieldMapping("agent_id"),
        "parent_task_id": FieldMapping("parent_task_id"),
        "role": FieldMapping("role"),
        "provider": FieldMapping("provider"),
        "status": FieldMapping("status"),
        "current_step": FieldMapping("current_step"),
        "last_message_summary": FieldMapping("last_message_summary"),
        "owned_paths": FieldMapping(
            "owned_paths",
            decode=_decode_string_tuple,
            encode=_encode_string_tuple,
        ),
        "command": FieldMapping(
            "command",
            decode=_decode_string_tuple,
            encode=_encode_string_tuple,
        ),
        "pid": FieldMapping("pid"),
        "started_at": FieldMapping("started_at"),
        "updated_at": FieldMapping("updated_at"),
        "finished_at": FieldMapping("finished_at"),
        "last_heartbeat_at": FieldMapping("last_heartbeat_at"),
        "error": FieldMapping("error"),
    },
)


__all__ = ["AGENT_RECORD_MAPPER"]
