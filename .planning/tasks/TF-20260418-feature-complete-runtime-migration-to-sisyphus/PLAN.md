# Plan

## Implementation Plan

1. Migrate the non-evolution core runtime modules into `src/sisyphus` and leave `taskflow` core imports as compatibility aliases.
2. Migrate MCP and evolution implementations into `src/sisyphus` and preserve legacy `taskflow` module paths.
3. Finish the ownership inversion by moving the CLI implementation into `src/sisyphus` and tightening the legacy compatibility boundary.
4. Record the final migration state, verification coverage, and closed slice tasks in the umbrella artifact.

## Risks

- Package ownership changes can silently regress legacy imports if module identity shifts.
- Resource packaging and launcher paths can break even when plain imports still succeed.
- Persisted identifiers such as `.taskflow.toml` and protocol strings must remain stable through the migration.

## Test Strategy

### Normal Cases

- [x] Canonical `sisyphus` imports own the core runtime, MCP, evolution, and CLI surfaces.
- [x] Legacy `taskflow` imports continue to resolve to the same runtime implementations used by `sisyphus`.

### Edge Cases

- [x] Template resources, MCP schema/resources, and evolution helpers remain available after the ownership move.
- [x] Legacy `.taskflow.toml` fallback and compatibility-sensitive protocol identifiers remain intentionally unchanged.

### Exception Cases

- [x] Focused regressions across taskflow compatibility, MCP, evolution, event bus, and golden fixtures catch remaining package-boundary drift.

## Verification Mapping

- `Canonical and legacy module paths resolve to the same final runtime boundary` -> `env PYTHONPYCACHEPREFIX=/tmp/pycache ./.venv/bin/python -c "import importlib; print(importlib.import_module('taskflow.cli') is importlib.import_module('sisyphus.cli')); print(importlib.import_module('taskflow.mcp_server') is importlib.import_module('sisyphus.mcp_server')); print(importlib.import_module('taskflow.evolution.constraints') is importlib.import_module('sisyphus.evolution.constraints')); print(importlib.import_module('taskflow.api') is importlib.import_module('sisyphus.api'))"`
- `Focused regression coverage stays green after the full staged migration` -> `env PYTHONPYCACHEPREFIX=/tmp/pycache ./.venv/bin/python -m unittest tests.test_taskflow tests.test_mcp_core tests.test_mcp_adapter tests.test_mcp_server tests.test_evolution tests.test_event_bus tests.test_golden -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
