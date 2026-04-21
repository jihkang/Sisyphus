# Plan

## Implementation Plan

1. Extend merge receipt recording so it can attempt close handoff when a task is already verified and only waiting on promotion completion.
2. Surface close handoff results through daemon, API, and MCP projections so promotion recording is no longer a detached side note.
3. Cover both paths in regression tests: unverified tasks remain open after receipt recording, and verified promotion-pending tasks close automatically once the receipt lands.

## Risks

- The conversation request may omit edge conditions that still matter in the current codebase.
- The change may affect adjacent flows if the requested behavior touches shared state.

## Test Strategy

### Normal Cases

- [x] Verified promotion-pending tasks close automatically when a merge receipt is recorded

### Edge Cases

- [x] Unverified tasks keep the recorded receipt without triggering premature closeout

### Exception Cases

- [x] Close handoff metadata stays visible in daemon/API/MCP results even when no close happens

## Verification Mapping

- `Verified promotion-pending tasks close automatically when a merge receipt is recorded` -> `python -m unittest tests.test_sisyphus tests.test_mcp_core`
- `Unverified tasks keep the recorded receipt without triggering premature closeout` -> `python -m unittest tests.test_sisyphus tests.test_mcp_core`
- `Close handoff metadata stays visible in daemon/API/MCP results even when no close happens` -> `python -m unittest tests.test_sisyphus tests.test_mcp_core`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
