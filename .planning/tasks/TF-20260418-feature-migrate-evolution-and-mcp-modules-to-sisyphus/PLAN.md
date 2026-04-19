# Plan

## Implementation Plan

1. Copy `mcp_core`, `mcp_adapter`, `mcp_server`, and `evolution/*` implementation files from `src/taskflow` into `src/sisyphus`.
2. Make `sisyphus` the implementation owner for those surfaces and flip `taskflow` to compatibility mode.
3. Add regression coverage for legacy `taskflow` imports resolving to the moved `sisyphus` implementations.
4. Validate the moved MCP and evolution surfaces with smoke imports and focused unit suites, then record the commands in the task artifact.

## Risks

- Nested package aliasing for `taskflow.evolution.*` can silently fail if submodules are not rebound explicitly.
- Tests and callers that patch legacy module paths can break if `taskflow` no longer resolves to the same module objects.
- MCP launcher behavior can regress if canonical module ownership changes without preserving tool and resource semantics.

## Test Strategy

### Normal Cases

- [x] Canonical `sisyphus.mcp_*` and `sisyphus.evolution.*` imports resolve to live local implementations.
- [x] Legacy `taskflow.mcp_*` imports and `taskflow.evolution.constraints` resolve to the same implementations used by `sisyphus`.

### Edge Cases

- [x] The MCP server still resolves repo roots and exposes the same tool and resource contracts after the ownership move.
- [x] Evolution planning, dataset, harness, constraint, fitness, and report helpers remain non-mutating where the tests expect read-only behavior.

### Exception Cases

- [x] Focused regressions across taskflow compatibility, MCP, evolution, event bus, and golden fixtures catch import-boundary breakage before the next migration slice.

## Verification Mapping

- `Canonical MCP and evolution imports succeed` -> `env PYTHONPYCACHEPREFIX=/tmp/pycache ./.venv/bin/python -c "import importlib; import sisyphus.mcp_core, sisyphus.mcp_adapter, sisyphus.mcp_server, sisyphus.evolution, sisyphus.evolution.constraints; print(importlib.import_module('taskflow.mcp_core') is importlib.import_module('sisyphus.mcp_core')); print(importlib.import_module('taskflow.mcp_adapter') is importlib.import_module('sisyphus.mcp_adapter')); print(importlib.import_module('taskflow.mcp_server') is importlib.import_module('sisyphus.mcp_server')); print(importlib.import_module('taskflow.evolution.constraints') is importlib.import_module('sisyphus.evolution.constraints')); print(importlib.import_module('taskflow.evolution').plan_evolution_run is importlib.import_module('sisyphus.evolution').plan_evolution_run)"`
- `Legacy taskflow compatibility and canonical MCP/evolution behavior remain intact` -> `env PYTHONPYCACHEPREFIX=/tmp/pycache ./.venv/bin/python -m unittest tests.test_taskflow tests.test_mcp_core tests.test_mcp_adapter tests.test_mcp_server tests.test_evolution -v`
- `Adjacent regressions stay green after the package move` -> `env PYTHONPYCACHEPREFIX=/tmp/pycache ./.venv/bin/python -m unittest tests.test_event_bus tests.test_golden -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
