# Fix Plan

## Root Cause Hypothesis

- Retry path incorrectly normalizes unicode bytes.

## Fix Strategy

1. Reproduce
2. Add regression test
3. Fix parser normalization

## Test Strategy

### Normal Cases

- [x] Baseline retry flow still works

### Edge Cases

- [x] Unicode payload is retried correctly

### Exception Cases

- [x] Timeout in downstream parser is surfaced

## Verification Mapping

- `Baseline retry flow still works` -> `unit_test`
- `Unicode payload is retried correctly` -> `integration_test`
- `Timeout in downstream parser is surfaced` -> `manual_check`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
