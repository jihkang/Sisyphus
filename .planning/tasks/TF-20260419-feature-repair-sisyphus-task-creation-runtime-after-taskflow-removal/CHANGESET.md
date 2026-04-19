# Changeset

- Added `src/sisyphus/mcp_launcher.py` to centralize MCP launcher environment/config generation and pin the runtime to the current repo `src/` tree.
- Updated `init-mcp.sh` to register Codex and Claude MCP servers with `PYTHONPATH=<repo>/src`.
- Refreshed MCP setup docs and wrapper examples so manual registrations also prefer the current Sisyphus source tree.
- Added `tests/test_mcp_launcher.py` to lock the launcher env/config contract and the active template root away from legacy taskflow paths.
