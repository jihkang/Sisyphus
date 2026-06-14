from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import json

from .events import utc_now
from .fingerprint import stable_json_hash


EPISODE_TRACE_SCHEMA_VERSION = "sisyphus.episode_trace.v1"
DEFAULT_EPISODE_DIR = Path("artifacts") / "episodes"


@dataclass(frozen=True, slots=True)
class EpisodeStep:
    episode_id: str
    task_id: str
    step: int
    timestamp: str
    state_ref: str
    observation_hash: str
    action: dict[str, object]
    result: dict[str, object]
    state_diff: dict[str, object]
    actor: dict[str, object]
    schema_version: str = EPISODE_TRACE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "task_id": self.task_id,
            "step": self.step,
            "timestamp": self.timestamp,
            "state_ref": self.state_ref,
            "observation_hash": self.observation_hash,
            "actor": self.actor,
            "action": self.action,
            "result": self.result,
            "state_diff": self.state_diff,
        }


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
    observation_hash = str(observation.get("observation_hash") or stable_json_hash(observation))
    return EpisodeStep(
        episode_id=episode_id,
        task_id=task_id,
        step=step,
        timestamp=timestamp or utc_now(),
        state_ref=f"task://{task_id}/observation",
        observation_hash=observation_hash,
        actor=dict(actor or {}),
        action={
            "name": action_name,
            "arguments": dict(arguments or {}),
        },
        result=dict(result or {}),
        state_diff=diff_task_state(state_before, state_after),
    )


def append_episode_step(task_dir: Path, episode_step: EpisodeStep) -> Path:
    path = task_dir / DEFAULT_EPISODE_DIR / f"{episode_step.episode_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(episode_step.to_dict(), separators=(",", ":"), sort_keys=True))
        handle.write("\n")
    return path


def diff_task_state(
    before: Mapping[str, object],
    after: Mapping[str, object],
    *,
    keys: tuple[str, ...] | None = None,
) -> dict[str, object]:
    selected_keys = keys or tuple(sorted(set(before.keys()) | set(after.keys())))
    diff: dict[str, object] = {}
    for key in selected_keys:
        before_value = before.get(key)
        after_value = after.get(key)
        if before_value != after_value:
            diff[key] = [before_value, after_value]
    return diff


__all__ = [
    "DEFAULT_EPISODE_DIR",
    "EPISODE_TRACE_SCHEMA_VERSION",
    "EpisodeStep",
    "append_episode_step",
    "build_episode_step",
    "diff_task_state",
]
