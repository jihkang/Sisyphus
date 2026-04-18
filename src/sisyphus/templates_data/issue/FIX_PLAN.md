# Fix Plan

## Root Cause Hypothesis

- Hypothesis 1

## Fix Strategy

1. Confirm root cause
2. Add or update regression test
3. Implement fix
4. Re-run audit

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
