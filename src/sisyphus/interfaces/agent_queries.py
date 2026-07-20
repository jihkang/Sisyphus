from __future__ import annotations

from pathlib import Path

from ..composition.agents import build_agent_management_service
from ..config import SisyphusConfig
from ..domain.agent import DEFAULT_STALE_AFTER_SECONDS
from .agent_presenter import present_agent


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


__all__ = ["list_agents"]
