# Plan

## Implementation Plan

1. Inspect the current code path related to: implement promotion and invalidation evaluator.
2. Implement the requested behavior for: Implement PromotionDecision and InvalidationRecord models plus evaluator helpers for FeatureChangeArtifact. The slice should compute candidate, verified, promotable, stale, and invalid states from slot bindings, verification claims, lineage, approvals, and invariant checks. Keep scope to policy evaluation and tests, not full workflow integration or live mutation routing..
3. Update tests and task docs to match the final behavior.

## Risks

- The conversation request may omit edge conditions that still matter in the current codebase.
- The change may affect adjacent flows if the requested behavior touches shared state.

## Test Strategy

### Normal Cases

- [ ] Requested conversation workflow succeeds

### Edge Cases

- [ ] Minimal valid input still behaves predictably

### Exception Cases

- [ ] Unexpected failure surfaces an actionable error

## Verification Mapping

- `Requested conversation workflow succeeds` -> `taskflow verify`
- `Minimal valid input still behaves predictably` -> `targeted regression test`
- `Unexpected failure surfaces an actionable error` -> `manual review`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
