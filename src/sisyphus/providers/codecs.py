from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class LocalAgentRunView(Protocol):
    schema_version: str
    status: str
    summary: str
    error: str | None
    observation_hash: str | None
    request_digest: str | None
    started_at: str
    finished_at: str
    action_count: int
    protocol_error_count: int
    blocked_action_count: int
    compaction_count: int
    completion_facts: dict[str, object]
    events: tuple[dict[str, object], ...]


class LocalAgentBenchmarkCaseView(Protocol):
    fixture_id: str
    title: str
    kind: str
    passed: bool
    reason: str
    status: str
    terminal_finish: bool
    completion_ready: bool
    expected_changed_paths: tuple[str, ...]
    actual_changed_paths: tuple[str, ...]
    action_count: int
    protocol_error_count: int
    blocked_action_count: int
    compaction_count: int
    duration_ms: int


class LocalAgentBenchmarkRunView(Protocol):
    schema_version: str
    provider_profile: dict[str, object]
    started_at: str
    finished_at: str
    cases: Sequence[LocalAgentBenchmarkCaseView]

    @property
    def passed(self) -> bool: ...


def encode_local_agent_run_result(value: LocalAgentRunView) -> dict[str, object]:
    return {
        "schema_version": value.schema_version,
        "status": value.status,
        "summary": value.summary,
        "error": value.error,
        "observation_hash": value.observation_hash,
        "request_digest": value.request_digest,
        "started_at": value.started_at,
        "finished_at": value.finished_at,
        "action_count": value.action_count,
        "protocol_error_count": value.protocol_error_count,
        "blocked_action_count": value.blocked_action_count,
        "compaction_count": value.compaction_count,
        "completion_facts": value.completion_facts,
        "events": list(value.events),
    }


def encode_local_agent_benchmark_case_result(
    value: LocalAgentBenchmarkCaseView,
) -> dict[str, object]:
    return {
        "fixture_id": value.fixture_id,
        "title": value.title,
        "kind": value.kind,
        "passed": value.passed,
        "reason": value.reason,
        "status": value.status,
        "terminal_finish": value.terminal_finish,
        "completion_ready": value.completion_ready,
        "expected_changed_paths": list(value.expected_changed_paths),
        "actual_changed_paths": list(value.actual_changed_paths),
        "action_count": value.action_count,
        "protocol_error_count": value.protocol_error_count,
        "blocked_action_count": value.blocked_action_count,
        "compaction_count": value.compaction_count,
        "duration_ms": value.duration_ms,
    }


def encode_local_agent_benchmark_run_result(
    value: LocalAgentBenchmarkRunView,
) -> dict[str, object]:
    coding = tuple(case for case in value.cases if case.kind == "coding")
    safety = tuple(case for case in value.cases if case.kind == "safety")
    passed_count = sum(1 for case in value.cases if case.passed)
    return {
        "schema_version": value.schema_version,
        "started_at": value.started_at,
        "finished_at": value.finished_at,
        "passed": value.passed,
        "provider": dict(value.provider_profile),
        "summary": {
            "fixture_count": len(value.cases),
            "passed_count": passed_count,
            "success_rate": _rate(passed_count, len(value.cases)),
            "coding_count": len(coding),
            "coding_passed_count": sum(1 for case in coding if case.passed),
            "coding_success_rate": _rate(
                sum(1 for case in coding if case.passed), len(coding)
            ),
            "safety_count": len(safety),
            "safety_passed_count": sum(1 for case in safety if case.passed),
            "safety_success_rate": _rate(
                sum(1 for case in safety if case.passed), len(safety)
            ),
            "action_count": sum(case.action_count for case in value.cases),
            "protocol_error_count": sum(
                case.protocol_error_count for case in value.cases
            ),
            "blocked_action_count": sum(
                case.blocked_action_count for case in value.cases
            ),
            "compaction_count": sum(case.compaction_count for case in value.cases),
            "duration_ms": sum(case.duration_ms for case in value.cases),
        },
        "cases": [
            encode_local_agent_benchmark_case_result(case) for case in value.cases
        ],
    }


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


__all__ = [
    "LocalAgentBenchmarkCaseView",
    "LocalAgentBenchmarkRunView",
    "LocalAgentRunView",
    "encode_local_agent_benchmark_case_result",
    "encode_local_agent_benchmark_run_result",
    "encode_local_agent_run_result",
]
