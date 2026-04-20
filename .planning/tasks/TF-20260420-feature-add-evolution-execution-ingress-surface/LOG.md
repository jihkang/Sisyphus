# Log

## Timeline

- Created task through CLI fallback because the live MCP `sisyphus.request_task` runtime still resolved stale `src/taskflow/templates_data/...` paths.
- Narrowed this slice to operator-facing evolution execution ingress only. Existing persisted-run inspection commands stay in place.
- Added a shared `execute_evolution_surface(...)` helper so CLI and MCP share one execution contract and one failure-reporting path.
- Exposed `sisyphus evolution execute` and `sisyphus.evolution_execute` without changing the existing persisted-run inspection commands.
- Updated evolution docs and added regression coverage for success, explicit input wiring, and duplicate run-id failure reporting.

## Notes

- Internal evolution execution already exists in `src/sisyphus/evolution/orchestrator.py` via `execute_evolution_run(...)`.
- Existing CLI and MCP surfaces expose persisted run inspection only; they do not start new runs.

## Follow-ups

- Keep the stale MCP `request_task` runtime issue tracked separately from this ingress slice.
