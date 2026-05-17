# Fix Plan

## Root Cause Hypothesis

- Retry path incorrectly normalizes unicode bytes.

## Fix Strategy

1. Reproduce
2. Add regression test
3. Fix parser normalization

## Design Evaluation

- Design Mode: `none`
- Decision Reason: `existing contract only`
- Confidence: `medium`
- Layer Impact: `layer-preserving`
- Layer Decision Reason: `fixture uses existing verify behavior`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `n/a`

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
