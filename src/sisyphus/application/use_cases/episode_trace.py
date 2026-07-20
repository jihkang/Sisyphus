from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ..episode_trace import EpisodeStep, build_episode_step, check_episode_steps
from ..ports.clock import ClockPort
from ..ports.episode_trace import EpisodeTracePort


@dataclass(slots=True)
class EpisodeTraceService:
    store: EpisodeTracePort
    clock: ClockPort

    def record(
        self,
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
        episode_step = build_episode_step(
            episode_id=episode_id,
            task_id=task_id,
            step=step if step is not None else self.store.next_step(episode_id),
            observation=observation,
            action_name=action_name,
            arguments=arguments,
            result=result,
            state_before=state_before,
            state_after=state_after,
            actor=actor,
            timestamp=timestamp or self.clock.now(),
        )
        return episode_step, self.store.append(episode_step)

    def check(
        self,
        *,
        task_id: str | None = None,
        episode_id: str | None = None,
    ) -> dict[str, object]:
        return check_episode_steps(
            self.store.read(episode_id=episode_id),
            task_id=task_id,
            episode_id=episode_id,
        )


__all__ = ["EpisodeTraceService"]
