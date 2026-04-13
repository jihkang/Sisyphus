# Brief

## Task

- Task ID: `TF-20260413-feature-understand-mcp-next-work`
- Type: `feature`
- Slug: `understand-mcp-next-work`
- Branch: `feat/understand-mcp-next-work`

## Problem

- The requested Sisyphus-first workflow exposed a real MCP contract bug before self-evolution work could continue.
- `sisyphus.request_task` returns an integer `orchestrated` count from `taskflow.api.TaskRequestResult`, but the MCP output schema advertised that field as a boolean.
- The MCP connector enforces the declared output schema, so the request could create a task as a side effect and still fail the client call with an output validation error.

## Desired Outcome

- `sisyphus.request_task` can be used reliably over MCP without output validation failures.
- The MCP schema matches the actual runtime payload shape.
- Regression coverage exists so the mismatch does not reappear while the MCP control plane is expanded for self-evolution work.

## Acceptance Criteria

- [x] `sisyphus.request_task` exposes `orchestrated` as an integer in the MCP output schema.
- [x] `SisyphusMcpCoreService.call_tool("sisyphus.request_task", ...)` is covered by a regression test that asserts the integer payload shape.
- [x] MCP-focused regression tests pass with the updated schema.

## Constraints

- Preserve the current `TaskRequestResult` meaning for `orchestrated`; do not silently coerce it to a boolean.
- Keep the fix narrow so the next self-evolution workstream can build on a stable MCP control plane.
