# Plan

## Implementation Plan

1. Detect stacked child tasks when a parent merge receipt is recorded and mark those children as needing retarget and reverification.
2. Persist retarget metadata in the promotion bundle and surface affected child task ids through daemon, API, and MCP results.
3. Stop the workflow daemon from auto-advancing `retarget_required` tasks and cover the new blocked phase with regression tests.

## Risks

- The conversation request may omit edge conditions that still matter in the current codebase.
- The change may affect adjacent flows if the requested behavior touches shared state.

## Test Strategy

### Normal Cases

- [x] Parent merge recording marks stacked child tasks for retarget and reverification

### Edge Cases

- [x] Non-stacked or already-finished tasks are left untouched while affected children stay blocked for operator action

### Exception Cases

- [x] Merge receipt results surface affected child task ids so operator follow-up is explicit

## Verification Mapping

- `Parent merge recording marks stacked child tasks for retarget and reverification` -> `python -m unittest tests.test_sisyphus tests.test_mcp_core`
- `Non-stacked or already-finished tasks are left untouched while affected children stay blocked for operator action` -> `python -m unittest tests.test_sisyphus tests.test_mcp_core`
- `Merge receipt results surface affected child task ids so operator follow-up is explicit` -> `python -m unittest tests.test_sisyphus tests.test_mcp_core`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
