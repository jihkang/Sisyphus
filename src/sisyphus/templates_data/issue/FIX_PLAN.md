# Fix Plan

## Root Cause Hypothesis

- Hypothesis 1

## Fix Strategy

1. Confirm root cause
2. Add or update regression test
3. Implement fix
4. Re-run audit

## Design Evaluation

- Design Mode: `none | light | full`
- Decision Reason: `existing contract only / crosses a few modules / introduces a new layer`
- Confidence: `low/medium/high`
- Layer Impact: `layer-preserving | layer-touching | layer-reshaping | layer-adding`
- Layer Decision Reason: `n/a`
- Required Design Artifacts: `none | connection_diagram, sequence_diagram, boundary_note`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `n/a`

## Test Strategy

### Normal Cases

- [ ] Baseline behavior still works

### Edge Cases

- [ ] Edge case 1

### Exception Cases

- [ ] Exception case 1

## Verification Mapping

- `Baseline behavior still works` -> `unit_test`
- `Edge case 1` -> `integration_test`
- `Exception case 1` -> `manual_check`

## External LLM Review

- Required: `yes/no`
- Provider: `codex/claude/other`
- Purpose: `root-cause challenge / edge-case review / regression review`
- Trigger: `before close / after second failed audit / parser/state-machine issue`
