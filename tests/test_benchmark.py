from __future__ import annotations

import json
import sys
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.benchmark import (
    BENCHMARK_METRICS,
    BENCHMARK_MODES,
    BENCHMARK_SCENARIOS,
    BenchmarkFixtureError,
    load_benchmark_fixtures,
    render_benchmark_markdown,
    run_benchmark_suite,
)


class BenchmarkTests(unittest.TestCase):
    def test_default_fixture_suite_covers_required_scenarios_and_modes(self) -> None:
        fixtures = load_benchmark_fixtures(PROJECT_ROOT / "benchmarks" / "tasks")

        self.assertEqual({fixture.scenario for fixture in fixtures}, set(BENCHMARK_SCENARIOS))
        for fixture in fixtures:
            self.assertEqual({result.mode for result in fixture.results}, set(BENCHMARK_MODES))

    def test_run_benchmark_suite_returns_stable_metrics(self) -> None:
        result = run_benchmark_suite(PROJECT_ROOT / "benchmarks" / "tasks")

        self.assertEqual(result.fixture_count, len(BENCHMARK_SCENARIOS))
        self.assertEqual(result.mode_count, len(BENCHMARK_MODES))
        for mode in BENCHMARK_MODES:
            self.assertEqual(set(result.metrics[mode]), set(BENCHMARK_METRICS))
        self.assertLess(result.metrics["sisyphus_full_trace"]["false_close_rate"], result.metrics["plain_agent"]["false_close_rate"])
        self.assertGreater(
            result.metrics["sisyphus_full_trace"]["reproducibility_score"],
            result.metrics["plain_agent"]["reproducibility_score"],
        )

    def test_failure_gated_proves_sisyphus_blocks_false_close(self) -> None:
        result = run_benchmark_suite(PROJECT_ROOT / "benchmarks" / "tasks")
        scenarios = {scenario["scenario"]: scenario for scenario in result.to_dict()["scenarios"]}
        failure = scenarios["failure_gated"]["results"]

        self.assertTrue(failure["plain_agent"]["false_close"])
        self.assertTrue(failure["plain_agent"]["close_succeeded"])
        for mode in BENCHMARK_MODES:
            if mode == "plain_agent":
                continue
            self.assertFalse(failure[mode]["false_close"])
            self.assertFalse(failure[mode]["close_succeeded"])

    def test_spec_drift_detected_before_close_for_harness_modes(self) -> None:
        result = run_benchmark_suite(PROJECT_ROOT / "benchmarks" / "tasks")
        scenarios = {scenario["scenario"]: scenario for scenario in result.to_dict()["scenarios"]}
        drift = scenarios["spec_drift"]["results"]

        self.assertFalse(drift["plain_agent"]["spec_drift_detected"])
        self.assertTrue(drift["plain_agent"]["false_close"])
        for mode in ("sisyphus_basic", "sisyphus_observation", "sisyphus_observation_evidence", "sisyphus_full_trace"):
            self.assertTrue(drift[mode]["spec_drift_detected"])
            self.assertFalse(drift[mode]["close_succeeded"])

    def test_markdown_renderer_is_concise_and_includes_modes(self) -> None:
        result = run_benchmark_suite(PROJECT_ROOT / "benchmarks" / "tasks")

        markdown = render_benchmark_markdown(result)

        self.assertIn("# Sisyphus Harness Benchmark", markdown)
        self.assertIn("| Mode | Task Success | Verify Pass |", markdown)
        self.assertIn("sisyphus_full_trace", markdown)

    def test_invalid_fixture_reports_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            (fixture_dir / "bad.json").write_text(
                json.dumps(
                    {
                        "schema_version": "sisyphus.benchmark.fixtures.v1",
                        "fixtures": [{"scenario": "unknown"}],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(BenchmarkFixtureError, "unknown benchmark scenario"):
                load_benchmark_fixtures(fixture_dir)


if __name__ == "__main__":
    unittest.main()
