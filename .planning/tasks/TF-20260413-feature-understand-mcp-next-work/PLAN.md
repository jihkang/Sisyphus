# Plan

## Implementation Plan

1. Read the Sisyphus MCP resources, architecture docs, MCP setup docs, and core runtime files to identify the first concrete blocker for the self-evolution control plane.
2. Repair the `sisyphus.request_task` MCP schema so it matches the real `TaskRequestResult` payload returned by `taskflow.api.request_task`.
3. Add regression coverage in `tests/test_mcp_core.py` for both the advertised schema and the tool payload returned by `SisyphusMcpCoreService`.
4. Run the MCP, event bus, and request/daemon regression tests from the project virtual environment.

## Risks

- A schema-only patch can mask a deeper semantic mismatch if the runtime payload is later changed without updating tests.
- MCP clients may cache server processes, so local code verification must rely on unit tests rather than assuming hot reload.

## Test Strategy

### Normal Cases

- [x] `sisyphus.request_task` exposes an integer `orchestrated` field through the MCP tool definition.

### Edge Cases

- [x] A `request_task` call that returns `orchestrated=0` still validates and is preserved as an integer.

### Exception Cases

- [x] MCP regressions outside the request path remain green after the schema change.

## Verification Mapping

- `sisyphus.request_task exposes an integer orchestrated field through the MCP tool definition.` -> `./.venv/bin/python -m unittest tests.test_mcp_core -v`
- `A request_task call that returns orchestrated=0 still validates and is preserved as an integer.` -> `./.venv/bin/python -m unittest tests.test_mcp_core -v`
- `MCP regressions outside the request path remain green after the schema change.` -> `./.venv/bin/python -m unittest tests.test_mcp_core tests.test_mcp_server tests.test_event_bus tests.test_taskflow.TaskflowDaemonTests tests.test_taskflow.TaskflowNewTests -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
