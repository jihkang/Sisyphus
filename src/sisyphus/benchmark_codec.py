from __future__ import annotations

from typing import Protocol


BENCHMARK_SCHEMA_VERSION = "sisyphus.benchmark.v1"

BENCHMARK_MODES = (
    "plain_agent",
    "sisyphus_basic",
    "sisyphus_observation",
    "sisyphus_observation_evidence",
    "sisyphus_full_trace",
)


class BenchmarkRunView(Protocol):
    fixture_count: int
    mode_count: int
    metrics: dict[str, dict[str, float]]
    scenarios: tuple[dict[str, object], ...]


def encode_benchmark_run_result(value: BenchmarkRunView) -> dict[str, object]:
    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "fixture_count": value.fixture_count,
        "mode_count": value.mode_count,
        "modes": list(BENCHMARK_MODES),
        "metrics": value.metrics,
        "scenarios": list(value.scenarios),
    }


__all__ = [
    "BENCHMARK_MODES",
    "BENCHMARK_SCHEMA_VERSION",
    "BenchmarkRunView",
    "encode_benchmark_run_result",
]
