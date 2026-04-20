# Log

## Timeline

- Created task via CLI fallback because live MCP `request_task` was still broken after reconnect.
- Confirmed the checked-in source resolves templates from `sisyphus/templates_data`, while the live MCP runtime still reports the removed `src/taskflow/templates_data/feature` path.
- Narrowed the scope to runtime/bootstrap/import precedence rather than template rendering logic itself.
- Switched MCP registration to a repo-local bootstrap script so reconnects import `src/sisyphus` before loading `sisyphus.mcp_server`.
- Added bootstrap inspection and launcher regression coverage, plus a debug log entry for the loaded `mcp_server.py` path.
- Updated `init-mcp.sh` to health-check the repo virtualenv, auto-run `uv sync`, and rebuild `.venv` after backing up a broken environment when the bootstrap cannot execute.
- Rebuilt the local `.venv` automatically during `init-mcp.sh --codex-only`; the previous environment was preserved at `.venv.broken.20260420203413`.
- Verified fresh bootstrap execution now resolves `/Users/jihokang/Documents/Sisyphus/src/sisyphus/mcp_server.py` and `/Users/jihokang/Documents/Sisyphus/src/sisyphus/templates_data`.
- Verified a fresh stdio MCP server against the root repo no longer fails on `taskflow/templates_data`; it advanced to git ref locking, showing template resolution was repaired.
- Verified end-to-end `sisyphus.request_task` success in a temporary local clone at `/tmp/sisyphus-mcp-probe-repo`, producing task `TF-20260420-feature-direct-mcp-bootstrap-probe-temp-clone-20260420`.

## Notes

- `./init-mcp.sh --codex-only` updates the Codex MCP registration, but that alone does not repair the live server behavior.
- The current conversation-scoped MCP process remained stale even after re-registration; fresh clients start the corrected server, which is the expected reconnect behavior.
- The repair scope stays limited to MCP bootstrap and runtime health. The direct request flow itself was not changed.

## Follow-ups

- The preserved backup environment `.venv.broken.20260420203413` is local operator state and is not part of the repo change.
