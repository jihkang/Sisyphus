# Plan

## Implementation Plan

1. Copy the non-evolution core runtime implementation modules and template assets from `src/taskflow` into `src/sisyphus`.
2. Flip package ownership so `sisyphus` re-exports local implementations while `taskflow` becomes a compatibility alias surface for the moved core modules.
3. Keep compatibility-sensitive identifiers stable and defer CLI, MCP, and evolution migration to later slices.
4. Add focused regression coverage and record the verification commands in the task artifact.

## Risks

- Import aliasing can silently regress if canonical and legacy package surfaces drift apart during later migration slices.
- Template resource loading can break if package data is only present under one package name.
- Over-eager renames of persisted identifiers would create behavioral regressions even if imports still succeed.

## Test Strategy

### Normal Cases

- [x] `import sisyphus` exposes the library API from local `sisyphus` implementations.
- [x] Legacy imports for moved core modules such as `taskflow.api`, `taskflow.agents`, `taskflow.workflow`, and `taskflow.templates` resolve to `sisyphus` implementations.

### Edge Cases

- [x] Template resource lookup succeeds from canonical `sisyphus` package data after the module move.
- [x] Compatibility-sensitive names remain unchanged where persistence depends on them, including `.taskflow.toml` fallback handling and `taskflow.event.v1`.

### Exception Cases

- [x] Focused regressions across taskflow, event bus, MCP, and golden fixtures catch import or packaging breakage before the next migration slice lands.

## Verification Mapping

- `Canonical sisyphus library imports succeed` -> `env PYTHONPYCACHEPREFIX=/tmp/pycache ./.venv/bin/python -c "import sisyphus, taskflow, sisyphus.templates, taskflow.agents, taskflow.api; print(sisyphus.__version__); print(taskflow.request_task is sisyphus.request_task); print(taskflow.agents.__name__); print(taskflow.api.__name__); print(sisyphus.templates.template_root().name)"`
- `Legacy taskflow core imports resolve to sisyphus implementations` -> `env PYTHONPYCACHEPREFIX=/tmp/pycache ./.venv/bin/python -m unittest tests.test_taskflow -v`
- `Event bus, MCP surface, and golden fixtures still pass after the package inversion` -> `env PYTHONPYCACHEPREFIX=/tmp/pycache ./.venv/bin/python -m unittest tests.test_event_bus tests.test_mcp_server tests.test_golden -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
