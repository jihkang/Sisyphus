# Changeset

## Summary

- Added deterministic benchmark fixtures for `bugfix_basic`, `feature_small`, `refactor_safe`, `docs_sync`, `failure_gated`, `spec_drift`, and `promotion_ready`.
- Added a benchmark runner that aggregates task success, verification, close, false-close, conformance, drift detection, evidence, action count, unrelated diff, reproducibility, and human-intervention metrics.
- Added `sisyphus benchmark run` with default Markdown output and `--json`.
- Added regression tests for fixture coverage, metric stability, false-close prevention, spec drift detection, renderer output, invalid fixtures, and CLI parsing.

## Files

- `benchmarks/tasks/harness-fixtures.json`
- `src/sisyphus/benchmark.py`
- `src/sisyphus/cli.py`
- `tests/test_benchmark.py`
- `tests/test_sisyphus.py`

## Verification

- Targeted benchmark/parser tests passed.
- Benchmark JSON and Markdown CLI smoke tests passed.
- Full unittest suite passed: 347 tests.
- `git diff --check` passed.
