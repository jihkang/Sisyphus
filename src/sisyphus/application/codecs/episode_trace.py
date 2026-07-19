from __future__ import annotations

from ..episode_trace import EpisodeStep


def encode_episode_step(value: EpisodeStep) -> dict[str, object]:
    return {
        "schema_version": value.schema_version,
        "episode_id": value.episode_id,
        "task_id": value.task_id,
        "step": value.step,
        "timestamp": value.timestamp,
        "state_ref": value.state_ref,
        "observation_hash": value.observation_hash,
        "actor": value.actor,
        "action": value.action,
        "result": value.result,
        "state_before": value.state_before,
        "state_after": value.state_after,
        "state_diff": value.state_diff,
    }


__all__ = ["encode_episode_step"]
