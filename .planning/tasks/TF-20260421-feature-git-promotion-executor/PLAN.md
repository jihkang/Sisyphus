# Plan

## Implementation Plan

1. Extend `gitops.py` with the missing stage, commit, push, and remote inspection primitives that the promotion chain needs.
2. Implement `promotion.execute_promotion(...)` so promotable tasks can commit staged worktree changes, push the task branch, open a PR with `gh`, and persist an execution receipt plus first-class promotion state updates.
3. Add API and MCP surfaces for the executor and cover real git push plus mocked PR-open behavior in regression tests.

## Risks

- The conversation request may omit edge conditions that still matter in the current codebase.
- The change may affect adjacent flows if the requested behavior touches shared state.

## Test Strategy

### Normal Cases

- [x] A promotable task can commit, push, and open a PR through the executor

### Edge Cases

- [x] A previously pushed task can resume PR creation without requiring new staged changes

### Exception Cases

- [x] Non-promotable tasks fail cleanly instead of entering the promotion chain

## Verification Mapping

- `A promotable task can commit, push, and open a PR through the executor` -> `python -m unittest tests.test_sisyphus tests.test_mcp_core`
- `A previously pushed task can resume PR creation without requiring new staged changes` -> `python -m unittest tests.test_sisyphus tests.test_mcp_core`
- `Non-promotable tasks fail cleanly instead of entering the promotion chain` -> `python -m unittest tests.test_sisyphus tests.test_mcp_core`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
