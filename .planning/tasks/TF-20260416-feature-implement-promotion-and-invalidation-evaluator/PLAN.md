# Plan

## Implementation Plan

1. Introduce typed `PromotionDecision` and `InvalidationRecord` models plus a small evaluation result type for `FeatureChangeArtifact` policy decisions.
2. Implement read-only evaluator helpers that derive `candidate`, `verified`, `promotable`, `stale`, and `invalid` outcomes from slot bindings, verification claims, invariants, approvals, and lineage compatibility.
3. Reuse the evaluator from the MCP projection surface so promotion and invalidation summaries come from the same policy logic instead of ad hoc resource formatting.
4. Add evaluator-focused unit coverage for promotable, stale, invalid, and pre-verify candidate projections without wiring the result into live workflow mutation.

## Risks

- Promotion policy can become misleading if required obligations are hard-coded in multiple places instead of centralized in one evaluator.
- Invalidation decisions must stay read-only in this slice; they should explain stale or invalid conditions, not trigger workflow transitions.

## Test Strategy

### Normal Cases

- [ ] A verified feature projection with required slots, passing claims, and matching lineage evaluates as promotable.

### Edge Cases

- [ ] A pre-verify feature projection stays in candidate state and reports the missing promotion obligations instead of failing evaluation.
- [ ] A lineage mismatch or stale child artifact produces a stale invalidation record without mutating the task.

### Exception Cases

- [ ] A failed invariant, failed verification claim, or selected implementation that is not part of the candidate set evaluates as invalid with explicit blocking reasons.

## Verification Mapping

- `A verified feature projection with required slots, passing claims, and matching lineage evaluates as promotable.` -> `python -m unittest -q tests.test_artifact_evaluator`
- `A pre-verify feature projection stays in candidate state and reports the missing promotion obligations instead of failing evaluation.` -> `python -m unittest -q tests.test_artifact_evaluator`
- `A lineage mismatch or stale child artifact produces a stale invalidation record without mutating the task.` -> `python -m unittest -q tests.test_artifact_evaluator`
- `A failed invariant, failed verification claim, or selected implementation that is not part of the candidate set evaluates as invalid with explicit blocking reasons.` -> `python -m unittest -q tests.test_artifact_evaluator`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
