from __future__ import annotations

from dataclasses import dataclass


TEST_FIRST_STATUS_SATISFIED = "satisfied"
TEST_FIRST_STATUS_INCOMPLETE = "incomplete"
TEST_FIRST_STATUS_VIOLATED = "violated"
TEST_FIRST_STATUS_NOT_RECORDED = "not_recorded"

TEST_FIRST_PHASE_SELECT_TESTS = "select_or_generate_tests"
TEST_FIRST_PHASE_RUN_BASELINE = "run_baseline_tests"
TEST_FIRST_PHASE_IMPLEMENT = "implement_change"
TEST_FIRST_PHASE_RERUN = "rerun_tests"
TEST_FIRST_PHASE_RECORD_EVIDENCE = "record_evidence"

TEST_FIRST_LOOP_PHASES = (
    TEST_FIRST_PHASE_SELECT_TESTS,
    TEST_FIRST_PHASE_RUN_BASELINE,
    TEST_FIRST_PHASE_IMPLEMENT,
    TEST_FIRST_PHASE_RERUN,
    TEST_FIRST_PHASE_RECORD_EVIDENCE,
)


@dataclass(frozen=True, slots=True)
class TestFirstPhaseEvent:
    phase: str
    step: int | None
    source: str

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "step": self.step,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class TestFirstEvaluation:
    status: str
    required_phases: tuple[str, ...]
    observed_phases: tuple[TestFirstPhaseEvent, ...]
    missing_phases: tuple[str, ...]
    violations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "required_phases": list(self.required_phases),
            "observed_phases": [event.to_dict() for event in self.observed_phases],
            "missing_phases": list(self.missing_phases),
            "violations": list(self.violations),
        }


def evaluate_test_first_loop(episode_steps: list[dict[str, object]]) -> TestFirstEvaluation:
    events: list[TestFirstPhaseEvent] = []
    violations: list[str] = []
    for step in episode_steps:
        phase, source = _extract_phase(step)
        if phase is None:
            continue
        step_number = step.get("step")
        normalized_step = step_number if isinstance(step_number, int) else None
        if phase not in TEST_FIRST_LOOP_PHASES:
            violations.append(f"unknown test-first phase {phase!r} at step {normalized_step}")
            events.append(TestFirstPhaseEvent(phase=phase, step=normalized_step, source=source))
            continue
        events.append(TestFirstPhaseEvent(phase=phase, step=normalized_step, source=source))

    if not events:
        return TestFirstEvaluation(
            status=TEST_FIRST_STATUS_NOT_RECORDED,
            required_phases=TEST_FIRST_LOOP_PHASES,
            observed_phases=(),
            missing_phases=TEST_FIRST_LOOP_PHASES,
            violations=(),
        )

    observed_known = tuple(event for event in events if event.phase in TEST_FIRST_LOOP_PHASES)
    observed_phase_set = {event.phase for event in observed_known}
    missing = tuple(phase for phase in TEST_FIRST_LOOP_PHASES if phase not in observed_phase_set)
    violations.extend(_ordering_violations(observed_known))

    if violations:
        status = TEST_FIRST_STATUS_VIOLATED
    elif missing:
        status = TEST_FIRST_STATUS_INCOMPLETE
    else:
        status = TEST_FIRST_STATUS_SATISFIED

    return TestFirstEvaluation(
        status=status,
        required_phases=TEST_FIRST_LOOP_PHASES,
        observed_phases=tuple(events),
        missing_phases=missing,
        violations=tuple(violations),
    )


def _extract_phase(step: dict[str, object]) -> tuple[str | None, str]:
    action = step.get("action")
    if isinstance(action, dict):
        phase = action.get("test_first_phase")
        if isinstance(phase, str) and phase:
            return phase, "action.test_first_phase"
        arguments = action.get("arguments")
        if isinstance(arguments, dict):
            phase = arguments.get("test_first_phase")
            if isinstance(phase, str) and phase:
                return phase, "action.arguments.test_first_phase"

    result = step.get("result")
    if isinstance(result, dict):
        phase = result.get("test_first_phase")
        if isinstance(phase, str) and phase:
            return phase, "result.test_first_phase"
        nested = result.get("test_first")
        if isinstance(nested, dict):
            phase = nested.get("phase")
            if isinstance(phase, str) and phase:
                return phase, "result.test_first.phase"

    return None, ""


def _ordering_violations(events: tuple[TestFirstPhaseEvent, ...]) -> list[str]:
    violations: list[str] = []
    order = {phase: index for index, phase in enumerate(TEST_FIRST_LOOP_PHASES)}
    max_seen = -1
    previous_phase: str | None = None
    for event in events:
        current = order[event.phase]
        if current < max_seen:
            violations.append(
                f"phase {event.phase!r} at step {event.step} occurred after later phase {previous_phase!r}"
            )
        max_seen = max(max_seen, current)
        previous_phase = event.phase
    return violations


__all__ = [
    "TEST_FIRST_LOOP_PHASES",
    "TEST_FIRST_PHASE_IMPLEMENT",
    "TEST_FIRST_PHASE_RECORD_EVIDENCE",
    "TEST_FIRST_PHASE_RERUN",
    "TEST_FIRST_PHASE_RUN_BASELINE",
    "TEST_FIRST_PHASE_SELECT_TESTS",
    "TEST_FIRST_STATUS_INCOMPLETE",
    "TEST_FIRST_STATUS_NOT_RECORDED",
    "TEST_FIRST_STATUS_SATISFIED",
    "TEST_FIRST_STATUS_VIOLATED",
    "TestFirstEvaluation",
    "TestFirstPhaseEvent",
    "evaluate_test_first_loop",
]
