from __future__ import annotations

from typing import Protocol


class TestFirstPhaseEventView(Protocol):
    phase: str
    step: int | None
    source: str


class TestFirstEvaluationView(Protocol):
    status: str
    required_phases: tuple[str, ...]
    observed_phases: tuple[TestFirstPhaseEventView, ...]
    missing_phases: tuple[str, ...]
    violations: tuple[str, ...]


def encode_test_first_phase_event(
    value: TestFirstPhaseEventView,
) -> dict[str, object]:
    return {
        "phase": value.phase,
        "step": value.step,
        "source": value.source,
    }


def encode_test_first_evaluation(
    value: TestFirstEvaluationView,
) -> dict[str, object]:
    return {
        "status": value.status,
        "required_phases": list(value.required_phases),
        "observed_phases": [
            encode_test_first_phase_event(event) for event in value.observed_phases
        ],
        "missing_phases": list(value.missing_phases),
        "violations": list(value.violations),
    }


__all__ = [
    "TestFirstEvaluationView",
    "TestFirstPhaseEventView",
    "encode_test_first_evaluation",
    "encode_test_first_phase_event",
]
