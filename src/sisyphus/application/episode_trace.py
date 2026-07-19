from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from ..shared.digests import stable_json_hash


EPISODE_TRACE_SCHEMA_VERSION = "sisyphus.episode_trace.v1"
EPISODE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$")


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
    state_before: dict[str, object]
    state_after: dict[str, object]
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
            "state_before": self.state_before,
            "state_after": self.state_after,
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
    timestamp: str,
    actor: Mapping[str, object] | None = None,
) -> EpisodeStep:
    validate_episode_id(episode_id)
    observation_hash = str(
        observation.get("observation_hash") or stable_json_hash(observation)
    )
    return EpisodeStep(
        episode_id=episode_id,
        task_id=task_id,
        step=step,
        timestamp=timestamp,
        state_ref=f"task://{task_id}/observation",
        observation_hash=observation_hash,
        actor=dict(actor or {}),
        action={
            "name": action_name,
            "arguments": dict(_json_safe(arguments or {})),
        },
        result=dict(_json_safe(result or {})),
        state_before=dict(_json_safe(state_before)),
        state_after=dict(_json_safe(state_after)),
        state_diff=diff_task_state(state_before, state_after),
    )


def check_episode_steps(
    steps: list[dict[str, object]],
    *,
    task_id: str | None = None,
    episode_id: str | None = None,
) -> dict[str, object]:
    errors: list[dict[str, object]] = []
    actions: list[str] = []
    valid_steps = 0
    previous_step_by_episode: dict[str, int] = {}

    for index, step in enumerate(steps, start=1):
        if step.get("valid") is False:
            errors.append(
                {
                    "index": index,
                    "episode_id": step.get("episode_id"),
                    "error": step.get("error"),
                }
            )
            continue
        step_errors = _validate_episode_step(step, task_id=task_id)
        if step_errors:
            errors.extend(
                {
                    "index": index,
                    "episode_id": step.get("episode_id"),
                    "error": error,
                }
                for error in step_errors
            )
            continue

        episode = str(step["episode_id"])
        step_number = int(step["step"])
        previous_step = previous_step_by_episode.get(episode)
        if previous_step is not None and step_number <= previous_step:
            errors.append(
                {
                    "index": index,
                    "episode_id": episode,
                    "error": "step numbers must increase within an episode",
                }
            )
            continue
        previous_step_by_episode[episode] = step_number
        valid_steps += 1
        action = step.get("action")
        if isinstance(action, dict) and action.get("name"):
            actions.append(str(action["name"]))

    return {
        "ok": not errors,
        "task_id": task_id,
        "episode_id": episode_id,
        "episode_count": len(
            {str(step.get("episode_id")) for step in steps if step.get("episode_id")}
        ),
        "step_count": len(steps),
        "valid_step_count": valid_steps,
        "actions": actions,
        "errors": errors,
    }


def default_episode_id(task_id: str, *, actor_id: str | None = None) -> str:
    suffix = _safe_episode_segment(actor_id) if actor_id else None
    if suffix:
        return f"ep-{_safe_episode_segment(task_id)}-{suffix}"
    return f"ep-{_safe_episode_segment(task_id)}"


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


def validate_episode_id(episode_id: str) -> str:
    normalized = str(episode_id or "").strip()
    if EPISODE_ID_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"invalid episode id: {episode_id!r}")
    return normalized


def _validate_episode_step(
    step: Mapping[str, object],
    *,
    task_id: str | None,
) -> list[str]:
    errors: list[str] = []
    required = (
        "schema_version",
        "episode_id",
        "task_id",
        "step",
        "timestamp",
        "state_ref",
        "observation_hash",
        "action",
        "result",
        "state_before",
        "state_after",
        "state_diff",
    )
    for key in required:
        if key not in step:
            errors.append(f"missing required field: {key}")
    if step.get("schema_version") != EPISODE_TRACE_SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if task_id is not None and step.get("task_id") != task_id:
        errors.append("task_id mismatch")
    if not isinstance(step.get("step"), int):
        errors.append("step must be an integer")
    if not str(step.get("observation_hash", "")).startswith("sha256:"):
        errors.append("observation_hash must be a sha256 digest")
    for key in ("action", "result", "state_before", "state_after", "state_diff"):
        if not isinstance(step.get(key), dict):
            errors.append(f"{key} must be an object")
    return errors


def _safe_episode_segment(value: str | None) -> str:
    segment = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "unknown")).strip("-")
    return segment or "unknown"


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


__all__ = [
    "EPISODE_ID_PATTERN",
    "EPISODE_TRACE_SCHEMA_VERSION",
    "EpisodeStep",
    "build_episode_step",
    "check_episode_steps",
    "default_episode_id",
    "diff_task_state",
    "validate_episode_id",
]
