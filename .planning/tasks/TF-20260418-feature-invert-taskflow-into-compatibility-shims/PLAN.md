# Plan

## Implementation Plan

1. Inspect which runtime surfaces still make `taskflow` look authoritative after the first two migration slices.
2. Move the remaining CLI implementation into `src/sisyphus` and widen the `taskflow` compatibility alias map so legacy imports resolve to canonical modules.
3. Extend compatibility tests to prove that `taskflow` and `sisyphus` paths share the same runtime module objects where required.
4. Validate the final compatibility boundary and record the commands in the task artifact.

## Risks

- Legacy tests and callers patch `taskflow.cli` symbols directly, so module identity matters for compatibility.
- Console entrypoints can regress if `taskflow.cli` no longer resolves to the same implementation as `sisyphus.cli`.
- Over-cleaning the package boundary could accidentally remove intentionally preserved compatibility behavior such as `.taskflow.toml` fallback.

## Test Strategy

### Normal Cases

- [x] Canonical `sisyphus.cli` owns the CLI implementation.
- [x] `taskflow.cli`, `taskflow.mcp_server`, and `taskflow.evolution.constraints` resolve to the same runtime implementations as their canonical `sisyphus` counterparts.

### Edge Cases

- [x] Existing tests that patch legacy `taskflow.cli` symbols continue to pass because the legacy import path resolves to the canonical module object.
- [x] Legacy `.taskflow.toml` fallback behavior and MCP/evolution compatibility remain intact while the ownership changes.

### Exception Cases

- [x] Focused regressions across taskflow compatibility, MCP, evolution, event bus, and golden fixtures catch any remaining package-boundary drift.

## Verification Mapping

- `Legacy taskflow entrypoints resolve to canonical sisyphus modules` -> `env PYTHONPYCACHEPREFIX=/tmp/pycache ./.venv/bin/python -c "import importlib; print(importlib.import_module('taskflow.cli') is importlib.import_module('sisyphus.cli')); print(importlib.import_module('taskflow.mcp_server') is importlib.import_module('sisyphus.mcp_server')); print(importlib.import_module('taskflow.evolution.constraints') is importlib.import_module('sisyphus.evolution.constraints'))"`
- `Taskflow compatibility and canonical runtime behavior remain intact` -> `env PYTHONPYCACHEPREFIX=/tmp/pycache ./.venv/bin/python -m unittest tests.test_taskflow tests.test_mcp_core tests.test_mcp_adapter tests.test_mcp_server tests.test_evolution tests.test_event_bus tests.test_golden -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
