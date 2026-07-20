from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from ..test_first_codec import (
    TestFirstEvaluationView,
    encode_test_first_evaluation,
    encode_test_first_phase_event,
)


EVAL_LOOP_SCHEMA_VERSION = "sisyphus.eval_loop.v1"
EVAL_LOOP_SHAPE = (
    "observation_t",
    "action_t",
    "transition_result_t",
    "observation_t_plus_1",
    "reward_t",
)


class EvalLoopResultView(Protocol):
    task_id: str
    mode: str
    observation_ref: str
    initial_observation_hash: str
    final_observation_hash: str
    episode_id: str | None
    step_count: int
    action_count: int
    terminal_status: str
    reward: Any
    metrics: dict[str, float]
    actions: tuple[dict[str, object], ...]
    test_first: TestFirstEvaluationView


def encode_eval_loop_result(value: EvalLoopResultView) -> dict[str, object]:
    return {
        "schema_version": EVAL_LOOP_SCHEMA_VERSION,
        "task_id": value.task_id,
        "mode": value.mode,
        "loop": {
            "shape": list(EVAL_LOOP_SHAPE),
            "test_first": encode_test_first_evaluation(value.test_first),
        },
        "observation": {
            "ref": value.observation_ref,
            "initial_hash": value.initial_observation_hash,
            "final_hash": value.final_observation_hash,
        },
        "episode": {
            "episode_id": value.episode_id,
            "step_count": value.step_count,
            "action_count": value.action_count,
        },
        "actions": list(value.actions),
        "outcome": {
            "terminal_status": value.terminal_status,
            "facts": asdict(value.reward.facts),
        },
        "reward": {
            "total": value.reward.total,
            "components": value.metrics,
            "penalties": dict(value.reward.penalties),
        },
        "metrics": value.metrics,
    }


__all__ = [
    "EVAL_LOOP_SCHEMA_VERSION",
    "EVAL_LOOP_SHAPE",
    "EvalLoopResultView",
    "encode_eval_loop_result",
    "encode_test_first_evaluation",
    "encode_test_first_phase_event",
]
