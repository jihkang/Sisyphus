# Verify

## Audit Summary

- Attempt: `<normalized>`
- Stage: `spec`
- Status: `failed`
- Result: `return to current task`

## Command Results

- No verify commands configured

## Test Coverage Check

- Normal cases defined: `no`
- Edge cases defined: `no`
- Exception cases defined: `no`
- Verification methods defined: `no`

## External LLM Review

- Required: `no`
- Status: `not_needed`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`

## Gates

- `DOC_INCOMPLETE`: BRIEF.md is incomplete
- `DOC_INCOMPLETE`: REPRO.md is incomplete
- `DOC_INCOMPLETE`: FIX_PLAN.md is incomplete
- `REGRESSION_TEST_MISSING`: issue task is missing a regression test target
- `SPEC_INCOMPLETE`: issue repro and regression target must be completed before audit
- `SPEC_INCOMPLETE`: task spec must define normal, edge, and exception cases before audit
- `VERIFICATION_MAPPING_MISSING`: verification mapping must be completed before audit
