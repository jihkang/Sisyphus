# Plan

## Implementation Plan

1. Add `src/taskflow/evolution/harness.py` with explicit dataclasses for planned metrics, evaluation slots, and the aggregate harness plan.
2. Implement a read-only planner that validates an `EvolutionRun` and `EvolutionDataset`, then returns baseline/candidate evaluation intent plus isolation requirements.
3. Support optional candidate target narrowing within the run scope while keeping deterministic ordering.
4. Add focused tests for happy-path plan creation, explicit candidate narrowing, invalid-scope rejection, and non-mutating behavior.
5. Update task docs and verify the slice with targeted unit tests.

## Risks

- If harness planning is underspecified now, later execution and reporting slices will need avoidable model churn.
- If candidate scope validation is weak, later runs may accidentally broaden evaluation beyond the selected run targets.

## Test Strategy

### Normal Cases

- [x] Harness planning returns baseline and candidate evaluation slots for a valid run and dataset.
- [x] Harness planning records isolation requirements and empty planned metrics/result containers without executing work.

### Edge Cases

- [x] Explicit candidate target narrowing stays within the run scope and preserves deterministic ordering.

### Exception Cases

- [x] Harness planning rejects mismatched repo roots or out-of-scope candidate targets and does not mutate repository files.

## Verification Mapping

- `Harness planning returns baseline and candidate evaluation slots for a valid run and dataset.` -> `./.venv/bin/python -m unittest tests.test_evolution -v`
- `Harness planning records isolation requirements and empty planned metrics/result containers without executing work.` -> `./.venv/bin/python -m unittest tests.test_evolution -v`
- `Explicit candidate target narrowing stays within the run scope and preserves deterministic ordering.` -> `./.venv/bin/python -m unittest tests.test_evolution -v`
- `Harness planning rejects mismatched repo roots or out-of-scope candidate targets and does not mutate repository files.` -> `./.venv/bin/python -m unittest tests.test_evolution -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
