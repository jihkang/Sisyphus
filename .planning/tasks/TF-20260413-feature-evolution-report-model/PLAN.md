# Plan

## Implementation Plan

1. Reuse the existing `EvolutionRun`, `EvolutionDataset`, and `EvolutionHarnessPlan` models as the stable input contract for reporting.
2. Add `src/taskflow/evolution/report.py` with a report model that summarizes run scope, dataset scope, evaluation summaries, guard outcomes, fitness output, and stable comparison placeholders.
3. Keep the report read-only and suitable for both plan-only and future executed runs, without adding MCP resources or branch materialization logic in this slice.
4. Extend `tests/test_evolution.py` with report coverage for planned, reviewable, and invalid-input paths.

## Risks

- The report needs to remain stable for both empty planned metrics and future executed metrics, so placeholder behavior must be explicit.
- Report summaries must stay aligned with guard and fitness results without reintroducing execution or storage concerns in this slice.

## Test Strategy

### Normal Cases

- [x] A planned evolution run can be summarized into a stable report structure with dataset scope and explicit placeholders.
- [x] A scored candidate with accepted hard guards is surfaced as ready for review with attached comparison summaries.

### Edge Cases

- [x] Plan-only inputs keep report status in `planned` while still exposing the stable nested structure.

### Exception Cases

- [x] Mismatched run/dataset/harness inputs are rejected without mutating repository files.

## Verification Mapping

- `Planned run report structure is stable` -> `./.venv/bin/python -m unittest tests.test_evolution -v`
- `Reviewable candidate report is projected correctly` -> `./.venv/bin/python -m unittest tests.test_evolution -v`
- `Invalid report inputs are rejected without repo mutation` -> `./.venv/bin/python -m unittest tests.test_evolution -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
