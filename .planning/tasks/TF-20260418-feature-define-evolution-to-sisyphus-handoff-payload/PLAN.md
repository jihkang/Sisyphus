# Plan

## Implementation Plan

1. Review the current Sisyphus task request surface and the current evolution outputs to identify the minimum request payload the bridge will need.
2. Define the follow-up request contract as a reviewable handoff object rather than a generic callback signature.
3. Separate request semantics from receipt semantics so the same object is not treated as both task submission and execution proof.
4. Add or adjust tests and docs so the no-self-approval rule is encoded in the contract and its usage notes.

## Hard Risks

- If the handoff payload can implicitly trigger execution, evolution will bypass Sisyphus review gates.
- If the payload omits evidence or verification context, operators will not have enough information to review follow-up work.
- If the payload mixes request and receipt fields, later bridge code will blur submission, execution, and verification states.

## Safety Invariants

- The handoff payload represents a reviewable request only.
- Evolution may not be granted plan approval, spec freeze, or production execution authority through this payload.
- Receipt and verification records must remain downstream Sisyphus artifacts, not fields that mark the request as completed.

## Out Of Scope

- Actual bridge execution.
- Provider-wrapper invocation.
- Automatic approval, spec freeze, or promotion.
- CLI or MCP surface changes.

## Evidence Requirements

- Integration-facing type definitions for the handoff request.
- Updated docs that describe the handoff contract and the no-self-approval boundary.
- Regression coverage for required fields and contract semantics.

## Failure And Recovery

- If a candidate field is really a receipt field, move it out of the handoff request before plan approval.
- If operator review cannot be performed from the payload alone, revise the contract to carry the missing context instead of relying on implicit state.

## Test Strategy

### Normal Cases

- [ ] The handoff contract captures the context required to open a reviewable follow-up task request.

### Edge Cases

- [ ] The contract remains request-only and does not imply that execution, approval, or verification already happened.

### Exception Cases

- [ ] The contract does not encode a path for evolution to self-approve or self-freeze follow-up work.

## Verification Mapping

- `The handoff contract captures the context required to open a reviewable follow-up task request.` -> `targeted unit test in tests.test_evolution`
- `The contract remains request-only and does not imply that execution, approval, or verification already happened.` -> `manual review of type definitions and docs`
- `The contract does not encode a path for evolution to self-approve or self-freeze follow-up work.` -> `manual review of type definitions and docs`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
