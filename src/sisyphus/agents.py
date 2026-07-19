from __future__ import annotations

from functools import wraps
from pathlib import Path

from .application.commands.agent import RegisterAgentCommand, UpdateAgentCommand
from .application.use_cases.agents import AgentManagementError
from .composition.agents import build_agent_management_service
from .config import SisyphusConfig
from .domain.agent import (
    ACTIVE_AGENT_STATUSES,
    AGENT_STATUSES,
    DEFAULT_STALE_AFTER_SECONDS,
    FINAL_AGENT_STATUSES,
    AgentPolicyError,
)
from .infra.persistence import agent_repository
from .interfaces.agent_presenter import present_agent
from .shared.mappings import find_unknown_fields


class AgentTrackingError(RuntimeError):
    """Raised when agent lifecycle records cannot be managed safely."""


def guard_agent_updates(*allowed_fields: str):
    allowed = set(allowed_fields)

    def decorator(func):
        @wraps(func)
        def wrapper(
            repo_root: Path,
            config: SisyphusConfig,
            task_id: str,
            agent_id: str,
            **changes,
        ):
            unknown_fields = find_unknown_fields(changes, allowed)
            if unknown_fields:
                names = ", ".join(unknown_fields)
                raise AgentTrackingError(f"unknown agent update field(s): {names}")
            return func(repo_root, config, task_id, agent_id, **changes)

        return wrapper

    return decorator


def register_agent(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    agent_id: str,
    role: str,
    provider: str | None = None,
    current_step: str | None = None,
    last_message_summary: str | None = None,
    owned_paths: list[str] | None = None,
    command: list[str] | None = None,
    status: str = "running",
) -> dict:
    try:
        view = build_agent_management_service(repo_root, config).register(
            RegisterAgentCommand(
                task_id=task_id,
                agent_id=agent_id,
                role=role,
                provider=provider,
                current_step=current_step,
                last_message_summary=last_message_summary,
                owned_paths=tuple(owned_paths or ()),
                command=tuple(command or ()),
                status=status,
            )
        )
    except (AgentManagementError, AgentPolicyError) as error:
        raise AgentTrackingError(str(error)) from error
    return present_agent(view)


@guard_agent_updates(
    "status",
    "provider",
    "current_step",
    "last_message_summary",
    "owned_paths",
    "command",
    "pid",
    "error",
)
def update_agent(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    agent_id: str,
    **changes: object,
) -> dict:
    try:
        view = build_agent_management_service(repo_root, config).update(
            UpdateAgentCommand(
                task_id=task_id,
                agent_id=agent_id,
                status=_optional_text(changes.get("status")),
                provider=_optional_text(changes.get("provider")),
                current_step=_optional_text(changes.get("current_step")),
                last_message_summary=_optional_text(changes.get("last_message_summary")),
                owned_paths=_optional_tuple(changes.get("owned_paths")),
                command=_optional_tuple(changes.get("command")),
                pid=_optional_int(changes.get("pid")),
                error=_optional_text(changes.get("error")),
            )
        )
    except (AgentManagementError, AgentPolicyError) as error:
        raise AgentTrackingError(str(error)) from error
    return present_agent(view)


def load_agent_record(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    agent_id: str,
    stale_after_seconds: int | None = DEFAULT_STALE_AFTER_SECONDS,
) -> tuple[dict, Path]:
    try:
        view = build_agent_management_service(repo_root, config).get(
            task_id,
            agent_id,
            stale_after_seconds=stale_after_seconds,
        )
    except AgentPolicyError as error:
        raise AgentTrackingError(str(error)) from error
    return (
        present_agent(view),
        agent_repository.agent_file(repo_root, config.task_dir, task_id, agent_id),
    )


def list_agents(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    task_id: str | None = None,
    stale_after_seconds: int | None = DEFAULT_STALE_AFTER_SECONDS,
) -> list[dict]:
    views = build_agent_management_service(repo_root, config).list(
        task_id=task_id,
        stale_after_seconds=stale_after_seconds,
    )
    return [present_agent(view) for view in views]


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_tuple(value: object) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
        raise AgentTrackingError("agent list fields must contain strings")
    return tuple(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


__all__ = [
    "ACTIVE_AGENT_STATUSES",
    "AGENT_STATUSES",
    "DEFAULT_STALE_AFTER_SECONDS",
    "FINAL_AGENT_STATUSES",
    "AgentTrackingError",
    "guard_agent_updates",
    "list_agents",
    "load_agent_record",
    "register_agent",
    "update_agent",
]
