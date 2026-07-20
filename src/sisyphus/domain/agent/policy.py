from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Mapping

from .models import ACTIVE_AGENT_STATUSES, AGENT_STATUSES, FINAL_AGENT_STATUSES, Agent


class AgentPolicyError(ValueError):
    pass


def validate_agent_id(agent_id: str) -> None:
    if not agent_id or any(marker in agent_id for marker in ("/", "\\", "..")):
        raise AgentPolicyError(f"invalid agent id: {agent_id}")


def validate_agent_status(status: str) -> None:
    if status not in AGENT_STATUSES:
        allowed = ", ".join(sorted(AGENT_STATUSES))
        raise AgentPolicyError(f"invalid agent status `{status}`; expected one of: {allowed}")


def create_agent(
    *,
    task_id: str,
    agent_id: str,
    role: str,
    provider: str | None,
    status: str,
    current_step: str | None,
    last_message_summary: str | None,
    owned_paths: tuple[str, ...],
    command: tuple[str, ...],
    now: str,
) -> Agent:
    validate_agent_id(agent_id)
    validate_agent_status(status)
    return Agent(
        agent_id=agent_id,
        parent_task_id=task_id,
        role=role,
        provider=provider,
        status=status,
        current_step=current_step,
        last_message_summary=last_message_summary,
        owned_paths=owned_paths,
        command=command,
        started_at=now,
        updated_at=now,
        finished_at=now if status in FINAL_AGENT_STATUSES else None,
        last_heartbeat_at=now,
    )


def update_agent_state(agent: Agent, changes: Mapping[str, object], *, now: str) -> Agent:
    status_value = changes.get("status")
    status = str(status_value) if status_value is not None else agent.status
    validate_agent_status(status)
    values: dict[str, object] = {}
    for field in (
        "status",
        "provider",
        "current_step",
        "last_message_summary",
        "owned_paths",
        "command",
        "pid",
        "error",
    ):
        value = changes.get(field)
        if value is not None:
            values[field] = value
    values["updated_at"] = now
    if status in ACTIVE_AGENT_STATUSES:
        values["last_heartbeat_at"] = now
        values["finished_at"] = None
    elif agent.finished_at is None:
        values["finished_at"] = now
        values["pid"] = None
    return replace(agent, **values)


def effective_agent_status(
    agent: Agent,
    *,
    stale_after_seconds: int | None,
    now: str,
) -> str:
    if stale_after_seconds is None or agent.status not in ACTIVE_AGENT_STATUSES:
        return agent.status
    heartbeat = agent.last_heartbeat_at or agent.updated_at
    if not heartbeat:
        return "stale"
    try:
        last_seen = datetime.fromisoformat(heartbeat.replace("Z", "+00:00"))
        current = datetime.fromisoformat(now.replace("Z", "+00:00"))
    except ValueError:
        return "stale"
    if (current - last_seen).total_seconds() > stale_after_seconds:
        return "stale"
    return agent.status


__all__ = [
    "AgentPolicyError",
    "create_agent",
    "effective_agent_status",
    "update_agent_state",
    "validate_agent_id",
    "validate_agent_status",
]
