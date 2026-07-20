from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


LOCAL_AGENT_BENCHMARK_FIXTURE_SCHEMA_VERSION = (
    "sisyphus.local_agent_benchmark.fixtures.v1"
)
LOCAL_AGENT_BENCHMARK_SCHEMA_VERSION = "sisyphus.local_agent_benchmark.v1"
LOCAL_AGENT_BENCHMARK_KINDS = ("coding", "safety")
DEFAULT_LOCAL_AGENT_BENCHMARK_FIXTURE_FILE = (
    Path("benchmarks") / "local-agent" / "fixtures.json"
)


class LocalAgentBenchmarkFixtureError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LocalAgentBenchmarkFixture:
    fixture_id: str
    title: str
    kind: str
    prompt: str
    files: tuple[tuple[str, str], ...]
    owned_paths: tuple[str, ...]
    test_commands: tuple[str, ...]
    expected_changed_paths: tuple[str, ...]
    min_compactions: int = 0


@dataclass(frozen=True, slots=True)
class LocalAgentBenchmarkCaseResult:
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


@dataclass(frozen=True, slots=True)
class LocalAgentBenchmarkRunResult:
    provider_profile: dict[str, object]
    started_at: str
    finished_at: str
    cases: tuple[LocalAgentBenchmarkCaseResult, ...]
    schema_version: str = LOCAL_AGENT_BENCHMARK_SCHEMA_VERSION

    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)


__all__ = [
    "DEFAULT_LOCAL_AGENT_BENCHMARK_FIXTURE_FILE",
    "LOCAL_AGENT_BENCHMARK_FIXTURE_SCHEMA_VERSION",
    "LOCAL_AGENT_BENCHMARK_KINDS",
    "LOCAL_AGENT_BENCHMARK_SCHEMA_VERSION",
    "LocalAgentBenchmarkCaseResult",
    "LocalAgentBenchmarkFixture",
    "LocalAgentBenchmarkFixtureError",
    "LocalAgentBenchmarkRunResult",
]
