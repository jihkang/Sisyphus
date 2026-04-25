# Plan

## Implementation Plan

1. Extend the promotion bundle so it can persist stacked lineage details, explicit base overrides, and a human-readable explanation for the chosen base.
2. Teach the promotion executor to resolve base branches in this order: explicit override, open parent task branch, merged parent merge target, then task base fallback.
3. Persist the chosen base explanation into execution receipts and cover all three resolution paths with regression tests.

## Risks

- The conversation request may omit edge conditions that still matter in the current codebase.
- The change may affect adjacent flows if the requested behavior touches shared state.

## Test Strategy

### Normal Cases

- [x] Stacked promotion uses an open parent task branch as the PR base

### Edge Cases

- [x] Merged parent lineage falls back to the parent merge target and explicit base override still wins

### Exception Cases

- [x] Unresolved parent lineage still leaves a reconstructable fallback reason instead of silently choosing a base

## Verification Mapping

- `Stacked promotion uses an open parent task branch as the PR base` -> `python -m unittest tests.test_sisyphus`
- `Merged parent lineage falls back to the parent merge target and explicit base override still wins` -> `python -m unittest tests.test_sisyphus`
- `Unresolved parent lineage still leaves a reconstructable fallback reason instead of silently choosing a base` -> `python -m unittest tests.test_sisyphus`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
