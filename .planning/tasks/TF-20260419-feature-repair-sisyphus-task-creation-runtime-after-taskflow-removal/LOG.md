# Log

## Timeline

- Created the task through the CLI fallback because the live MCP runtime still pointed at a stale taskflow-era registration.
- Confirmed the in-repo source path already resolves templates through `src/sisyphus/templates_data`, which narrowed the bug to MCP launcher/runtime registration rather than core task creation code.
- Added a typed MCP launcher helper, pinned launcher `PYTHONPATH` to `<repo>/src`, updated MCP setup docs/examples, reran `./init-mcp.sh --codex-only`, and executed targeted regression tests.

## Notes

- `init-mcp.sh` now registers Codex and Claude MCP server configs with `PYTHONPATH` pointing at the current repo `src/` tree so stale installed package copies do not win import resolution.
- New launcher tests assert the generated env/config uses `sisyphus.mcp_server`, the repo `src/` path, and never falls back to taskflow template roots.
- After re-registering Codex MCP, the server continued responding and the debug log showed the refreshed server handling calls.

## Follow-ups

- Keep the future CLI/MCP evolution surface separate from launcher/runtime registration logic.
- If the operator still has an older external client registration, rerun `./init-mcp.sh` in that environment as well.
