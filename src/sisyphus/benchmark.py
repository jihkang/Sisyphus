from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
import json


BENCHMARK_SCHEMA_VERSION = "sisyphus.benchmark.v1"
BENCHMARK_FIXTURE_SCHEMA_VERSION = "sisyphus.benchmark.fixtures.v1"

BENCHMARK_SCENARIOS = (
    "bugfix_basic",
    "feature_small",
    "refactor_safe",
    "docs_sync",
    "failure_gated",
    "spec_drift",
    "promotion_ready",
)

BENCHMARK_MODES = (
    "plain_agent",
    "sisyphus_basic",
    "sisyphus_observation",
    "sisyphus_observation_evidence",
    "sisyphus_full_trace",
)

BENCHMARK_METRICS = (
    "task_success_rate",
    "verify_pass_rate",
    "close_success_rate",
    "false_close_rate",
    "conformance_green_rate",
    "spec_drift_detected_rate",
    "evidence_completeness",
    "action_count",
    "unrelated_diff_ratio",
    "reproducibility_score",
    "human_intervention_count",
)

DEFAULT_BENCHMARK_FIXTURE_DIR = Path("benchmarks") / "tasks"


class BenchmarkFixtureError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BenchmarkCaseResult:
    mode: str
    task_success: bool
    verify_passed: bool
    close_succeeded: bool
    false_close: bool
    conformance_green: bool
    spec_drift_detected: bool
    evidence_completeness: float
    action_count: int
    unrelated_diff_ratio: float
    reproducibility_score: float
    human_intervention_count: int


@dataclass(frozen=True, slots=True)
class BenchmarkFixture:
    scenario: str
    title: str
    drift_present: bool
    results: tuple[BenchmarkCaseResult, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkRunResult:
    fixture_count: int
    mode_count: int
    metrics: dict[str, dict[str, float]]
    scenarios: tuple[dict[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": BENCHMARK_SCHEMA_VERSION,
            "fixture_count": self.fixture_count,
            "mode_count": self.mode_count,
            "modes": list(BENCHMARK_MODES),
            "metrics": self.metrics,
            "scenarios": list(self.scenarios),
        }


def default_benchmark_fixture_dir(repo_root: Path) -> Path:
    return repo_root / DEFAULT_BENCHMARK_FIXTURE_DIR


def run_benchmark_suite(fixtures_dir: Path) -> BenchmarkRunResult:
    fixtures = load_benchmark_fixtures(fixtures_dir)
    return evaluate_benchmark_fixtures(fixtures)


def load_benchmark_fixtures(fixtures_dir: Path) -> tuple[BenchmarkFixture, ...]:
    if not fixtures_dir.exists():
        raise BenchmarkFixtureError(f"benchmark fixture directory does not exist: {fixtures_dir}")
    fixtures: list[BenchmarkFixture] = []
    for path in sorted(fixtures_dir.glob("*.json")):
        payload = _load_json_object(path)
        if payload.get("schema_version") != BENCHMARK_FIXTURE_SCHEMA_VERSION:
            raise BenchmarkFixtureError(f"unsupported benchmark fixture schema in {path}")
        items = payload.get("fixtures")
        if not isinstance(items, list):
            raise BenchmarkFixtureError(f"fixtures must be a list in {path}")
        for item in items:
            fixtures.append(_parse_fixture(item, path))
    if not fixtures:
        raise BenchmarkFixtureError(f"no benchmark fixtures found in {fixtures_dir}")
    _validate_fixture_set(fixtures)
    return tuple(fixtures)


def evaluate_benchmark_fixtures(fixtures: Iterable[BenchmarkFixture]) -> BenchmarkRunResult:
    fixture_list = tuple(fixtures)
    if not fixture_list:
        raise BenchmarkFixtureError("at least one benchmark fixture is required")

    metrics: dict[str, dict[str, float]] = {}
    for mode in BENCHMARK_MODES:
        mode_results = [_result_for_mode(fixture, mode) for fixture in fixture_list]
        drift_results = [
            _result_for_mode(fixture, mode)
            for fixture in fixture_list
            if fixture.drift_present
        ]
        metrics[mode] = {
            "task_success_rate": _rate(result.task_success for result in mode_results),
            "verify_pass_rate": _rate(result.verify_passed for result in mode_results),
            "close_success_rate": _rate(result.close_succeeded for result in mode_results),
            "false_close_rate": _rate(result.false_close for result in mode_results),
            "conformance_green_rate": _rate(result.conformance_green for result in mode_results),
            "spec_drift_detected_rate": _rate(result.spec_drift_detected for result in drift_results),
            "evidence_completeness": _mean(result.evidence_completeness for result in mode_results),
            "action_count": _mean(result.action_count for result in mode_results),
            "unrelated_diff_ratio": _mean(result.unrelated_diff_ratio for result in mode_results),
            "reproducibility_score": _mean(result.reproducibility_score for result in mode_results),
            "human_intervention_count": _mean(result.human_intervention_count for result in mode_results),
        }

    return BenchmarkRunResult(
        fixture_count=len(fixture_list),
        mode_count=len(BENCHMARK_MODES),
        metrics=metrics,
        scenarios=tuple(_scenario_summary(fixture) for fixture in fixture_list),
    )


def render_benchmark_markdown(result: BenchmarkRunResult) -> str:
    lines = [
        "# Sisyphus Harness Benchmark",
        "",
        f"- Fixtures: `{result.fixture_count}`",
        f"- Modes: `{result.mode_count}`",
        "",
        "| Mode | Task Success | Verify Pass | Close Success | False Close | Drift Detected | Evidence | Actions | Reproducibility |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode in BENCHMARK_MODES:
        metrics = result.metrics[mode]
        lines.append(
            "| "
            + " | ".join(
                [
                    mode,
                    _format_rate(metrics["task_success_rate"]),
                    _format_rate(metrics["verify_pass_rate"]),
                    _format_rate(metrics["close_success_rate"]),
                    _format_rate(metrics["false_close_rate"]),
                    _format_rate(metrics["spec_drift_detected_rate"]),
                    _format_number(metrics["evidence_completeness"]),
                    _format_number(metrics["action_count"]),
                    _format_number(metrics["reproducibility_score"]),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BenchmarkFixtureError(f"invalid benchmark fixture JSON in {path}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise BenchmarkFixtureError(f"benchmark fixture root must be a JSON object: {path}")
    return payload


def _parse_fixture(item: object, source: Path) -> BenchmarkFixture:
    if not isinstance(item, Mapping):
        raise BenchmarkFixtureError(f"fixture entries must be JSON objects in {source}")
    scenario = str(item.get("scenario") or "")
    if scenario not in BENCHMARK_SCENARIOS:
        raise BenchmarkFixtureError(f"unknown benchmark scenario {scenario!r} in {source}")
    title = str(item.get("title") or scenario)
    drift_present = bool(item.get("drift_present"))
    results_payload = item.get("results")
    if not isinstance(results_payload, Mapping):
        raise BenchmarkFixtureError(f"fixture {scenario} must define mode results")

    result_modes = set(str(key) for key in results_payload)
    expected_modes = set(BENCHMARK_MODES)
    if result_modes != expected_modes:
        missing = sorted(expected_modes - result_modes)
        unknown = sorted(result_modes - expected_modes)
        raise BenchmarkFixtureError(
            f"fixture {scenario} mode mismatch; missing={missing}, unknown={unknown}"
        )

    return BenchmarkFixture(
        scenario=scenario,
        title=title,
        drift_present=drift_present,
        results=tuple(
            _parse_case_result(mode, results_payload[mode], source, scenario)
            for mode in BENCHMARK_MODES
        ),
    )


def _parse_case_result(
    mode: str,
    payload: object,
    source: Path,
    scenario: str,
) -> BenchmarkCaseResult:
    if not isinstance(payload, Mapping):
        raise BenchmarkFixtureError(f"fixture {scenario}/{mode} result must be a JSON object in {source}")
    return BenchmarkCaseResult(
        mode=mode,
        task_success=_bool_field(payload, "task_success", source, scenario, mode),
        verify_passed=_bool_field(payload, "verify_passed", source, scenario, mode),
        close_succeeded=_bool_field(payload, "close_succeeded", source, scenario, mode),
        false_close=_bool_field(payload, "false_close", source, scenario, mode),
        conformance_green=_bool_field(payload, "conformance_green", source, scenario, mode),
        spec_drift_detected=_bool_field(payload, "spec_drift_detected", source, scenario, mode),
        evidence_completeness=_float_field(payload, "evidence_completeness", source, scenario, mode),
        action_count=_int_field(payload, "action_count", source, scenario, mode),
        unrelated_diff_ratio=_float_field(payload, "unrelated_diff_ratio", source, scenario, mode),
        reproducibility_score=_float_field(payload, "reproducibility_score", source, scenario, mode),
        human_intervention_count=_int_field(payload, "human_intervention_count", source, scenario, mode),
    )


def _validate_fixture_set(fixtures: list[BenchmarkFixture]) -> None:
    scenarios = [fixture.scenario for fixture in fixtures]
    missing = sorted(set(BENCHMARK_SCENARIOS) - set(scenarios))
    if missing:
        raise BenchmarkFixtureError(f"missing benchmark scenarios: {missing}")


def _result_for_mode(fixture: BenchmarkFixture, mode: str) -> BenchmarkCaseResult:
    for result in fixture.results:
        if result.mode == mode:
            return result
    raise BenchmarkFixtureError(f"fixture {fixture.scenario} is missing mode {mode}")


def _scenario_summary(fixture: BenchmarkFixture) -> dict[str, object]:
    return {
        "scenario": fixture.scenario,
        "title": fixture.title,
        "drift_present": fixture.drift_present,
        "results": {
            result.mode: asdict(result)
            for result in fixture.results
        },
    }


def _bool_field(payload: Mapping[str, object], key: str, source: Path, scenario: str, mode: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise BenchmarkFixtureError(f"{scenario}/{mode}.{key} must be boolean in {source}")
    return value


def _float_field(payload: Mapping[str, object], key: str, source: Path, scenario: str, mode: str) -> float:
    value = payload.get(key)
    if not isinstance(value, (int, float)):
        raise BenchmarkFixtureError(f"{scenario}/{mode}.{key} must be numeric in {source}")
    number = float(value)
    if number < 0:
        raise BenchmarkFixtureError(f"{scenario}/{mode}.{key} must be non-negative in {source}")
    return number


def _int_field(payload: Mapping[str, object], key: str, source: Path, scenario: str, mode: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise BenchmarkFixtureError(f"{scenario}/{mode}.{key} must be integer in {source}")
    if value < 0:
        raise BenchmarkFixtureError(f"{scenario}/{mode}.{key} must be non-negative in {source}")
    return value


def _rate(values: Iterable[bool]) -> float:
    items = tuple(values)
    if not items:
        return 0.0
    return round(sum(1 for value in items if value) / len(items), 3)


def _mean(values: Iterable[float | int]) -> float:
    items = tuple(float(value) for value in values)
    if not items:
        return 0.0
    return round(sum(items) / len(items), 3)


def _format_rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def _format_number(value: float) -> str:
    return f"{value:.3g}"


__all__ = [
    "BENCHMARK_FIXTURE_SCHEMA_VERSION",
    "BENCHMARK_METRICS",
    "BENCHMARK_MODES",
    "BENCHMARK_SCHEMA_VERSION",
    "BENCHMARK_SCENARIOS",
    "BenchmarkCaseResult",
    "BenchmarkFixture",
    "BenchmarkFixtureError",
    "BenchmarkRunResult",
    "DEFAULT_BENCHMARK_FIXTURE_DIR",
    "default_benchmark_fixture_dir",
    "evaluate_benchmark_fixtures",
    "load_benchmark_fixtures",
    "render_benchmark_markdown",
    "run_benchmark_suite",
]
