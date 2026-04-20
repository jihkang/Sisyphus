# Brief

## Task

- Task ID: `TF-20260420-feature-repair-live-mcp-request-task-runtime-after-reconnect`
- Type: `feature`
- Slug: `repair-live-mcp-request-task-runtime-after-reconnect`
- Branch: `feat/repair-live-mcp-request-task-runtime-after-reconnect`

## Problem

- The live Sisyphus MCP server still fails `sisyphus.request_task` after reconnect.
- The failure resolves templates through the removed `src/taskflow/templates_data/feature` path even though the checked-in code now uses `sisyphus/templates_data`.
- Re-running `./init-mcp.sh --codex-only` updates the registration, but the active MCP runtime still behaves like a stale bootstrap or import path is winning.

## Desired Outcome

- The live MCP server resolves task templates through the canonical `sisyphus/templates_data` package path after reconnect.
- `sisyphus.request_task` succeeds without depending on the removed `taskflow` package tree.
- The runtime/bootstrap cause is captured so future reconnects do not silently regress to stale imports.

## Acceptance Criteria

- [ ] Live MCP `sisyphus.request_task` succeeds after reconnect in the root repository.
- [ ] The active MCP runtime no longer attempts to read `src/taskflow/templates_data/...`.
- [ ] Regression coverage exercises the runtime/bootstrap path that caused the stale template resolution.
- [ ] Task docs describe the actual runtime cause, fix, and verification commands.

## Constraints

- Scope the change to MCP bootstrap, import resolution, and related regression coverage.
- Do not change task creation semantics beyond the runtime path repair.
- Keep the fix compatible with the current `sisyphus` package layout and reconnect workflow.
