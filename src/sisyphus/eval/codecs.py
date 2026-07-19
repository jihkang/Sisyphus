from __future__ import annotations

from dataclasses import asdict

from .loop import EVAL_LOOP_SCHEMA_VERSION, EVAL_LOOP_SHAPE, EvalLoopResult
from ..test_first import TestFirstEvaluation, TestFirstPhaseEvent


def encode_test_first_phase_event(value: TestFirstPhaseEvent) -> dict[str, object]:
    return {
        "phase": value.phase,
        "step": value.step,
        "source": value.source,
    }


def encode_test_first_evaluation(value: TestFirstEvaluation) -> dict[str, object]:
    return {
        "status": value.status,
        "required_phases": list(value.required_phases),
        "observed_phases": [
            encode_test_first_phase_event(event) for event in value.observed_phases
        ],
        "missing_phases": list(value.missing_phases),
        "violations": list(value.violations),
    }


def encode_eval_loop_result(value: EvalLoopResult) -> dict[str, object]:
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
    "encode_eval_loop_result",
    "encode_test_first_evaluation",
    "encode_test_first_phase_event",
]
