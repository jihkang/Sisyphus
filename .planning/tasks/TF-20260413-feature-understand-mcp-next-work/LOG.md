# Log

## Timeline

- Created task from the MCP-first investigation request.
- Read the repo MCP schema, board, conformance board, and recent events before inspecting source files.
- Identified a live MCP failure: `sisyphus.request_task` produced an output validation error because the schema declared `orchestrated` as a boolean while the runtime returned an integer count.
- Updated the MCP schema and added regression coverage in `tests/test_mcp_core.py`.
- Ran the MCP, event bus, daemon, and task creation regression suites from the repository virtual environment.

## Notes

- The failed `request_task` MCP calls still created repository-local tasks as side effects; this confirmed the bug was in response validation, not task creation itself.
- Repository conformance for the active task remained `green` throughout this investigation.

## Follow-ups

- The next self-evolution slice can start from `src/taskflow/evolution/` once the MCP control plane is stable enough to create and inspect tasks reliably.
