from __future__ import annotations

from dataclasses import dataclass


DEFAULT_STALE_AFTER_SECONDS = 900
ACTIVE_AGENT_STATUSES = {"queued", "running", "waiting"}
FINAL_AGENT_STATUSES = {"completed", "failed", "cancelled"}
AGENT_STATUSES = ACTIVE_AGENT_STATUSES | FINAL_AGENT_STATUSES


@dataclass(frozen=True, slots=True)
class Agent:
    agent_id: str = ""
    parent_task_id: str = ""
    role: str = ""
    provider: str | None = None
    status: str = "running"
    current_step: str | None = None
    last_message_summary: str | None = None
    owned_paths: tuple[str, ...] = ()
    command: tuple[str, ...] = ()
    pid: int | None = None
    started_at: str | None = None
    updated_at: str | None = None
    finished_at: str | None = None
    last_heartbeat_at: str | None = None
    error: str | None = None


__all__ = [
    "ACTIVE_AGENT_STATUSES",
    "AGENT_STATUSES",
    "Agent",
    "DEFAULT_STALE_AFTER_SECONDS",
    "FINAL_AGENT_STATUSES",
]
