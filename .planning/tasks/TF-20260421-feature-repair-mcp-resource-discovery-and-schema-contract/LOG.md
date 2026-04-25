# Log

## Timeline

- Created task
- Inspected MCP server, core, adapter, and test surfaces to find where template discovery and schema publication diverged.
- Generalized template URI detection, added stable placeholder responses, and normalized markdown MIME handling for task/evolution resources.
- Added targeted regression coverage for discovery splitting, placeholder reads, and unavailable artifact resources.
- Ran focused and broader unittest suites to confirm the MCP contract changes did not regress adjacent flows.

## Notes

- `mcp_server.py` had hardcoded template detection for `task://<task-id>` only, which left evolution resource templates misclassified.
- `mcp_core.py` listed resources such as `promotion` and `changeset` that could still raise before later lifecycle stages materialized them.
- The MCP schema surface was missing `task://<task-id>/repro` even though the read path already supported it.

## Follow-ups

- Feed this stabilized resource/schema contract into `TF-20260421-feature-normalize-task-state-projections` so all task projections share one canonical state path.
