from __future__ import annotations

from pathlib import Path

from .episode_trace import (
    default_episode_id,
    next_episode_step,
    record_episode_step,
)
from ..infra.providers.receipts import persist_local_receipt
from .observation import build_task_observation


def persist_local_provider_receipt(
    repo_root: Path,
    config: object,
    task_id: str,
    agent_id: str,
    receipt: dict[str, object],
) -> None:
    persist_local_receipt(
        repo_root,
        config,
        task_id,
        agent_id,
        receipt,
        episode_recorder=record_local_agent_episode,
    )


def record_local_agent_episode(
    task: dict[str, object],
    task_dir: Path,
    agent_id: str,
    receipt: dict[str, object],
) -> None:
    raw_events = receipt.get("events")
    if not isinstance(raw_events, list):
        return
    events = [
        event
        for event in raw_events
        if isinstance(event, dict) and event.get("action")
    ]
    if not events:
        return
    episode_id = default_episode_id(str(task.get("id") or "unknown"), actor_id=agent_id)
    observation = build_task_observation(task, task_dir)
    state = dict(task)
    step_number = next_episode_step(task_dir, episode_id)
    for event in events:
        action_name = str(event.get("action") or "unknown")
        arguments = event.get("arguments") if isinstance(event.get("arguments"), dict) else {}
        test_first_phase = event.get("test_first_phase")
        if isinstance(test_first_phase, str):
            arguments = {**arguments, "test_first_phase": test_first_phase}
        result = event.get("result") if isinstance(event.get("result"), dict) else {}
        record_episode_step(
            task_dir,
            episode_id=episode_id,
            task_id=str(task.get("id") or ""),
            step=step_number,
            observation=observation,
            action_name=f"local_agent.{action_name}",
            arguments=arguments,
            result={
                "ok": bool(event.get("ok")),
                "blocked": bool(event.get("blocked")),
                **result,
            },
            state_before=state,
            state_after=state,
            actor={"interface": "local_provider", "agent_id": agent_id},
        )
        step_number += 1


__all__ = ["persist_local_provider_receipt", "record_local_agent_episode"]
