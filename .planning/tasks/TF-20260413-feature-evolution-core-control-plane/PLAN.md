# Plan

## Implementation Plan

1. Create the initial `src/taskflow/evolution/` package and define the stable public types for an evolution run.
2. Add a target registry for phase-1 safe text/policy assets, with explicit metadata pointing back to existing modules and symbols.
3. Implement a runner skeleton that validates selected targets, resolves the registry, and returns an in-memory run plan without filesystem writes.
4. Add focused tests for registry contents, explicit/default target selection, and non-mutating run creation.
5. Update task docs and verify the slice with targeted unit tests.

## Risks

- If target metadata is underspecified now, later MCP surface work will need avoidable refactors.
- If the runner reaches into live task state too early, the control plane boundary from the plan document will be violated.

## Test Strategy

### Normal Cases

- [x] The default registry exposes the expected phase-1 text/policy targets.
- [x] The runner can build an evolution run from the default registry without touching repository state.

### Edge Cases

- [x] The runner can build a run from an explicit subset of registered targets and preserves deterministic ordering.

### Exception Cases

- [x] The runner rejects unknown target ids with an actionable error instead of silently broadening scope.

## Verification Mapping

- `The default registry exposes the expected phase-1 text/policy targets.` -> `./.venv/bin/python -m unittest tests.test_evolution -v`
- `The runner can build an evolution run from the default registry without touching repository state.` -> `./.venv/bin/python -m unittest tests.test_evolution -v`
- `The runner can build a run from an explicit subset of registered targets and preserves deterministic ordering.` -> `./.venv/bin/python -m unittest tests.test_evolution -v`
- `The runner rejects unknown target ids with an actionable error instead of silently broadening scope.` -> `./.venv/bin/python -m unittest tests.test_evolution -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
