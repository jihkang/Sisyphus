# Plan

## Implementation Plan

1. Inventory remaining `taskflow` references and split them into live package aliasing versus intentionally preserved persisted compatibility.
2. Remove the live package alias layer by deleting `src/taskflow`, removing the `taskflow` console entrypoint, and stripping `sisyphus` of reverse aliasing.
3. Rewrite repo-local tests and live docs so they target `sisyphus` directly.
4. Validate that `taskflow` imports are gone while canonical `sisyphus` runtime behavior remains green.

## Risks

- Tests that patched `taskflow.*` symbols directly could fail even when runtime behavior is otherwise correct.
- Removing the legacy package can expose hidden import dependencies that were previously masked by aliasing.
- Persisted compatibility such as `.taskflow.toml` fallback must not be confused with live package aliasing.

## Test Strategy

### Normal Cases

- [x] Canonical `sisyphus` CLI, MCP, evolution, and runtime imports work after `src/taskflow` removal.
- [x] Repo-local tests patch and import `sisyphus.*` directly.

### Edge Cases

- [x] `import taskflow` no longer resolves after package removal.
- [x] `.sisyphus.toml` preference and `.taskflow.toml` fallback continue to work.
- [x] `taskflow.event.v1` remains unchanged as a persisted schema identifier.

### Exception Cases

- [x] Focused regressions across taskflow-removal-sensitive surfaces catch hidden dependency drift before close.

## Verification Mapping

- `Canonical sisyphus runtime imports succeed and taskflow is absent` -> `env PYTHONPYCACHEPREFIX=/tmp/pycache ./.venv/bin/python -c "import importlib; import sisyphus, sisyphus.cli, sisyphus.mcp_server, sisyphus.evolution.constraints; print(sisyphus.__version__); print(importlib.util.find_spec('taskflow'))"`
- `Focused runtime regressions remain green after removing src/taskflow` -> `env PYTHONPYCACHEPREFIX=/tmp/pycache ./.venv/bin/python -m unittest tests.test_taskflow tests.test_mcp_core tests.test_mcp_adapter tests.test_mcp_server tests.test_evolution tests.test_event_bus tests.test_golden -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
