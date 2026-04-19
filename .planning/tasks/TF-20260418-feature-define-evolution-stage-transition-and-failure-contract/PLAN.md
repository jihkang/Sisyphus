# Plan

## Implementation Plan

1. Review the current evolution helpers and identify the actual transition points that already exist conceptually: run planning, dataset build, harness planning, constraints, fitness, and report.
2. Define the initial read-only stage sequence and document later extension stages without implementing them yet.
3. For each initial stage, define the expected input contract, produced output, invariants, and failure shape.
4. Add or adjust tests and docs so the stage names and failure model stay stable for the orchestration task.

## Hard Risks

- If stage boundaries are vague, the orchestrator will invent its own intermediate states and drift from the docs.
- If failure does not preserve stage context and partial artifacts, operator review will lose reconstructability.
- If extension stages are treated as active runtime behavior too early, later bridge and promotion work will look implemented when it is not.

## Safety Invariants

- The initial stage model must match the current read-only slice only.
- Failure must be represented as stage-aware metadata, not just an exception message.
- The documented extension path must remain explicitly future work until later tasks implement it.

## Out Of Scope

- Actual harness execution.
- Follow-up bridge execution.
- Promotion or invalidation runtime logic.
- CLI or MCP surface changes.

## Evidence Requirements

- Type or contract definitions for stages and failure shape.
- Updated docs describing each stage, invariants, and failure semantics.
- Regression coverage for stage naming and failure representation.

## Failure And Recovery

- If a stage cannot be grounded in current helpers, drop it from the initial sequence and record it as future work.
- If a failure shape cannot preserve the stage and partial outputs, revise the contract before plan approval.

## Test Strategy

### Normal Cases

- [ ] The initial read-only stage sequence matches the current evolution flow and can be referenced by the orchestrator task.

### Edge Cases

- [ ] Future extension stages remain documented as future work rather than current runtime obligations.

### Exception Cases

- [ ] Failures preserve stage identity and partial-result context instead of collapsing into opaque exceptions.

## Verification Mapping

- `The initial read-only stage sequence matches the current evolution flow and can be referenced by the orchestrator task.` -> `targeted unit test in tests.test_evolution`
- `Future extension stages remain documented as future work rather than current runtime obligations.` -> `manual review of docs and type definitions`
- `Failures preserve stage identity and partial-result context instead of collapsing into opaque exceptions.` -> `targeted unit test in tests.test_evolution`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
