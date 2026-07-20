# Verify

## Audit Summary

- Attempt: `1/10`
- Stage: `audit`
- Status: `failed`
- Result: `return to current task`

## Command Results

- No verify commands configured

## Test Coverage Check

- Normal cases defined: `yes`
- Edge cases defined: `yes`
- Exception cases defined: `yes`
- Verification methods defined: `yes`

## Design Assessment

- Mode: `full`
- Layer impact: `layer-adding`
- Status: `appropriate`
- Replan required: `no`
- Missing artifacts: `none`
- Summary: `design depth matches the current task shape`

## External LLM Review

- Required: `yes`
- Status: `pending`
- Provider: `independent Codex reviewer`
- Purpose: `independent challenge of dependency direction, compatibility evidence, abstraction balance, and hidden side-effect regressions`
- Trigger: `after all migration tests pass and before final promotion`

## Gates

- `EXTERNAL_LLM_REVIEW_REQUIRED`: required external LLM review is not complete
