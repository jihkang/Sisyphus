from __future__ import annotations

import unittest

from sisyphus.providers import benchmark
from sisyphus.providers import benchmark_fixtures, benchmark_models, benchmark_rendering


class BenchmarkBoundaryTests(unittest.TestCase):
    def test_stable_benchmark_surface_reexports_canonical_boundaries(self) -> None:
        self.assertIs(
            benchmark.LocalAgentBenchmarkFixture,
            benchmark_models.LocalAgentBenchmarkFixture,
        )
        self.assertIs(
            benchmark.LocalAgentBenchmarkRunResult,
            benchmark_models.LocalAgentBenchmarkRunResult,
        )
        self.assertIs(
            benchmark.load_local_agent_benchmark_fixtures,
            benchmark_fixtures.load_local_agent_benchmark_fixtures,
        )
        self.assertIs(
            benchmark.render_local_agent_benchmark_markdown,
            benchmark_rendering.render_local_agent_benchmark_markdown,
        )


if __name__ == "__main__":
    unittest.main()
