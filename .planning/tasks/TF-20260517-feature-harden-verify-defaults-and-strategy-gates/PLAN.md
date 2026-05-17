# Plan

## Implementation Plan

1. Inspect `run_verify`, verify profile resolution, test-strategy checking, gate creation, and closeout dependencies.
2. Define the minimum effective verification contract for implementation tasks:
   - non-empty resolved verify commands, or
   - explicit evidence-backed verification methods with durable refs, or
   - explicit design/docs-only waiver.
3. Add gate codes for empty verify command sets, missing verification evidence, and unchecked strategy coverage.
4. Update verify flow so strategy items are checked only when supported by command results/evidence or waiver metadata.
5. Keep design/docs-only tasks verifyable with explicit justification and tests.
6. Add regression tests for passing command-backed verification, failing empty-command implementation tasks, and valid design-only waiver behavior.

## Risks

- Tightening verification can expose old task fixtures that relied on empty command sets.
- Overly strict policy could block legitimate design-only or planning-only work.
- Close/promotion flows may need minor updates if they assume verify can pass without command results.

## Design Evaluation

- Design Mode: `light`
- Decision Reason: `tightens existing verification authority without adding a new subsystem`
- Confidence: `high`
- Layer Impact: `layer-touching`
- Layer Decision Reason: `changes audit/verification gates used by lifecycle and closeout`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `n/a`

## Test Strategy

### Normal Cases

- [ ] Implementation task with configured verify commands passes and records command evidence.
- [ ] Test strategy items are marked checked when mapped command/evidence succeeds.

### Edge Cases

- [ ] Design/docs-only task with explicit waiver can verify without commands.
- [ ] Existing closeout flow accepts a task verified under the stronger policy.

### Exception Cases

- [ ] Implementation task with empty resolved verify commands fails closed.
- [ ] Strategy items without evidence or waiver stay unchecked and block verification.
- [ ] Invalid waiver metadata fails with an actionable gate.

## Verification Mapping

- `Command-backed verification passes` -> `python -m unittest tests.test_sisyphus.SisyphusVerifyTests -v`
- `Empty command implementation task fails` -> `python -m unittest tests.test_sisyphus.SisyphusVerifyTests -v`
- `Design/docs-only waiver passes` -> `python -m unittest tests.test_sisyphus.SisyphusVerifyTests -v`
- `Golden lifecycle fixtures stay coherent` -> `python -m unittest tests.test_golden -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
