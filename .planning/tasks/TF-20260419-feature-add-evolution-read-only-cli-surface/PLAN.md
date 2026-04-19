# Plan

## Implementation Plan

1. Inspect the current evolution runner/orchestrator artifacts and determine the minimum CLI contract needed for `run`, `status`, `report`, and `compare`.
2. Extend `src/sisyphus/cli.py` with a read-only `evolution` command group that delegates to the existing evolution modules without adding promotion or follow-up execution behavior.
3. Add targeted tests for parser wiring, command dispatch, and representative rendering/output paths over stored evolution run artifacts.
4. Update docs to show the new CLI surface and its read-only authority boundary.

## Risks

- The CLI surface may drift from current artifact contracts if it renders ad hoc fields instead of stable run/report data.
- Adding `run` alongside `status/report/compare` can accidentally broaden scope into MCP/event or follow-up execution work.
- Output formatting must remain operator-readable without locking future MCP/event surfaces into the same presentation model.

## Test Strategy

### Normal Cases

- [x] Operators can invoke `evolution run`, `status`, `report`, and `compare` against the current evolution contracts and stored run artifacts.

### Edge Cases

- [x] Status/report commands surface clear output when a run exists but later-stage artifacts are still pending.
- [x] Compare behaves predictably when baseline/candidate metrics are partial rather than complete.

### Exception Cases

- [x] Unknown run ids or missing report artifacts surface actionable CLI errors without mutating task state.

## Verification Mapping

- `Operators can invoke evolution run, status, report, and compare against the current evolution contracts and stored run artifacts.` -> `python -m unittest -q tests.test_sisyphus tests.test_evolution`
- `Status/report commands surface clear output when a run exists but later-stage artifacts are still pending.` -> `python -m unittest -q tests.test_evolution`
- `Compare behaves predictably when baseline/candidate metrics are partial rather than complete.` -> `python -m unittest -q tests.test_evolution`
- `Unknown run ids or missing report artifacts surface actionable CLI errors without mutating task state.` -> `targeted regression test`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
