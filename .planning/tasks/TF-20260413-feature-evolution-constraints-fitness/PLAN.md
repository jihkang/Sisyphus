# Plan

## Implementation Plan

1. Inspect the current code path related to: Implement evolution constraints and fitness.
2. Implement the requested behavior for: Implement the evolution constraints and fitness slice from docs/self-evolution-mcp-plan.md. Add the first read-only constraints and scoring layer for planned evolution runs and harness outputs, including hard guards for regressions in verify pass rate, conformance drift, unresolved warnings, MCP compatibility, and output contract stability. Keep the scope to model and evaluation logic only..
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
