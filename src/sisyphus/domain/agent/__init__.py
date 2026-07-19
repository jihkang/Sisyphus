from __future__ import annotations

from .models import (
    ACTIVE_AGENT_STATUSES,
    AGENT_STATUSES,
    Agent,
    DEFAULT_STALE_AFTER_SECONDS,
    FINAL_AGENT_STATUSES,
)


_REPOSITORY_EXPORTS = frozenset(
    {
        "ConcurrentAgentUpdateError",
        "agent_file",
        "list_agent_files",
        "read_agent_record",
        "save_agent_record",
        "update_agent_record",
    }
)


def __getattr__(name: str) -> object:
    if name not in _REPOSITORY_EXPORTS:
        raise AttributeError(name)
    from . import repository

    return getattr(repository, name)


__all__ = [
    "ACTIVE_AGENT_STATUSES",
    "AGENT_STATUSES",
    "Agent",
    "ConcurrentAgentUpdateError",
    "DEFAULT_STALE_AFTER_SECONDS",
    "FINAL_AGENT_STATUSES",
    "agent_file",
    "list_agent_files",
    "read_agent_record",
    "save_agent_record",
    "update_agent_record",
]
