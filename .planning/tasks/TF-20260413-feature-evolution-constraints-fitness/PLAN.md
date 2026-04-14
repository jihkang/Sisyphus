# Plan

## Implementation Plan

1. Inspect the existing `taskflow.evolution` run, dataset, and harness models so the new guard/scoring layer reuses the current read-only planning structures.
2. Add `src/taskflow/evolution/constraints.py` with hard-guard result models and evaluation logic for verify pass rate, drift count, unresolved warnings, MCP compatibility, and output contract stability.
3. Add `src/taskflow/evolution/fitness.py` with comparable metric normalization and weighted scoring that works for both plan-only and populated harness metrics.
4. Export the new models through `taskflow.evolution` and extend `tests/test_evolution.py` with normal, edge, and exception-path coverage.

## Risks

- Planned harness metrics are intentionally sparse, so the new layer must preserve a stable pending state instead of forcing scores from missing data.
- Future executed harness metrics should be able to reuse the same models without breaking the current read-only slice.

## Test Strategy

### Normal Cases

- [x] A candidate with stable verify rate, stable drift, bounded warning increase, and passing compatibility checks is accepted and receives a comparable fitness score.

### Edge Cases

- [x] Plan-only harness data without populated metrics remains in a pending guard/fitness state instead of fabricating results.
- [x] Warning thresholds allow controlled unresolved-warning increases without broadening the hard-guard scope.

### Exception Cases

- [x] Regressions in verify rate, drift, warnings, MCP compatibility, or output contract stability reject the candidate without mutating repository files.

## Verification Mapping

- `Accepted candidate receives a comparable fitness score` -> `./.venv/bin/python -m unittest tests.test_evolution -v`
- `Plan-only inputs remain pending and warning thresholds are respected` -> `./.venv/bin/python -m unittest tests.test_evolution -v`
- `Hard-guard regressions reject without repo mutation` -> `./.venv/bin/python -m unittest tests.test_evolution -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
