from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ..application.episode_trace import (
    EPISODE_TRACE_SCHEMA_VERSION,
    EpisodeStep,
    build_episode_step as build_episode_step_at,
    default_episode_id,
    diff_task_state,
)
from ..application.use_cases.episode_trace import EpisodeTraceService
from ..infra.clock import SystemClock
from ..infra.episode_trace import DEFAULT_EPISODE_DIR, RepositoryEpisodeTraceStore


def build_episode_trace_service(task_dir: Path) -> EpisodeTraceService:
    return EpisodeTraceService(
        store=RepositoryEpisodeTraceStore(task_dir),
        clock=SystemClock(),
    )


def build_episode_step(
    *,
    episode_id: str,
    task_id: str,
    step: int,
    observation: Mapping[str, object],
    action_name: str,
    arguments: Mapping[str, object] | None,
    result: Mapping[str, object] | None,
    state_before: Mapping[str, object],
    state_after: Mapping[str, object],
    actor: Mapping[str, object] | None = None,
    timestamp: str | None = None,
) -> EpisodeStep:
    return build_episode_step_at(
        episode_id=episode_id,
        task_id=task_id,
        step=step,
        observation=observation,
        action_name=action_name,
        arguments=arguments,
        result=result,
        state_before=state_before,
        state_after=state_after,
        actor=actor,
        timestamp=timestamp or SystemClock().now(),
    )


def record_episode_step(
    task_dir: Path,
    *,
    episode_id: str,
    task_id: str,
    step: int | None = None,
    observation: Mapping[str, object],
    action_name: str,
    arguments: Mapping[str, object] | None,
    result: Mapping[str, object] | None,
    state_before: Mapping[str, object],
    state_after: Mapping[str, object],
    actor: Mapping[str, object] | None = None,
    timestamp: str | None = None,
) -> tuple[EpisodeStep, Path]:
    return build_episode_trace_service(task_dir).record(
        episode_id=episode_id,
        task_id=task_id,
        step=step,
        observation=observation,
        action_name=action_name,
        arguments=arguments,
        result=result,
        state_before=state_before,
        state_after=state_after,
        actor=actor,
        timestamp=timestamp,
    )


def append_episode_step(task_dir: Path, episode_step: EpisodeStep) -> Path:
    return RepositoryEpisodeTraceStore(task_dir).append(episode_step)


def next_episode_step(task_dir: Path, episode_id: str) -> int:
    return RepositoryEpisodeTraceStore(task_dir).next_step(episode_id)


def read_episode_steps(
    task_dir: Path,
    *,
    episode_id: str | None = None,
) -> list[dict[str, object]]:
    return RepositoryEpisodeTraceStore(task_dir).read(episode_id=episode_id)


def check_episode_trace(
    task_dir: Path,
    *,
    task_id: str | None = None,
    episode_id: str | None = None,
) -> dict[str, object]:
    return build_episode_trace_service(task_dir).check(
        task_id=task_id,
        episode_id=episode_id,
    )


__all__ = [
    "DEFAULT_EPISODE_DIR",
    "EPISODE_TRACE_SCHEMA_VERSION",
    "EpisodeStep",
    "append_episode_step",
    "build_episode_step",
    "build_episode_trace_service",
    "check_episode_trace",
    "default_episode_id",
    "diff_task_state",
    "next_episode_step",
    "read_episode_steps",
    "record_episode_step",
]
