# Plan

## Implementation Plan

1. Add canonical `sisyphus.<submodule>` aliases.
   - Extend `src/sisyphus/__init__.py` so the main internal modules are available through `sisyphus.<submodule>`.
   - Add a canonical `sisyphus.evolution` package wrapper that re-exports the existing evolution surface and nested modules.
   - Keep `taskflow.*` imports untouched as compatibility shims.

2. Rename the main internal config symbol.
   - Introduce `SisyphusConfig` as the canonical config dataclass name.
   - Preserve `TaskflowConfig` as a backward-compatible alias.
   - Update internal modules to type against `SisyphusConfig`.

3. Rename obvious internal helper and wording.
   - Rename `_is_internal_taskflow_path` to `_is_internal_sisyphus_path`, with a backward-compatible alias.
   - Update remaining obvious `taskflow`-branded docstrings and internal wording where that does not refer to persisted or compatibility identifiers.

4. Move wrappers and tests to canonical imports where practical.
   - Update wrappers to import through `sisyphus.provider_wrapper`.
   - Update test modules to import through `sisyphus.*` for the main runtime modules.
   - Rename test class names from `Taskflow*` to `Sisyphus*` where doing so does not affect runtime behavior.

5. Verify compatibility.
   - Run targeted unittests for taskflow/task orchestration, MCP server behavior, event bus/config loading, evolution surface, and golden tests.
   - Confirm `taskflow` compatibility still works via unchanged legacy imports and script entrypoints.

## Risks

- Eager or partial submodule aliasing could break `import sisyphus.<submodule>` if package initialization is incomplete.
- Renaming internal symbols without keeping aliases would break compatibility for existing imports and tests.
- Some `taskflow` strings still intentionally refer to compatibility or persisted identifiers and must not be renamed accidentally.

## Test Strategy

### Normal Cases

- [ ] Canonical `sisyphus` submodule imports work for the main runtime modules and evolution package.
- [ ] Internal config typing and helper names use canonical `Sisyphus` naming without breaking behavior.

### Edge Cases

- [ ] Legacy `taskflow` imports continue to work after canonical aliasing is added.
- [ ] Evolution imports work from the canonical `sisyphus.evolution` surface, not only from `taskflow.evolution`.

### Exception Cases

- [ ] Persisted/protocol identifiers such as `taskflow.event.v1` and `TF-...` are not accidentally renamed.
- [ ] Compatibility strings that must stay legacy are not broken while canonical names are introduced.

## Verification Mapping

- `Canonical sisyphus submodule imports work for the main runtime modules and evolution package.` -> `python -m unittest tests.test_taskflow tests.test_mcp_server tests.test_evolution -v`
- `Internal config typing and helper names use canonical Sisyphus naming without breaking behavior.` -> `python -m unittest tests.test_taskflow tests.test_event_bus -v`
- `Legacy taskflow imports continue to work and persisted identifiers remain unchanged.` -> `python -m unittest tests.test_golden tests.test_mcp_adapter tests.test_mcp_core -v`
- `Compatibility and persisted identifiers are not renamed accidentally.` -> `manual review of diff`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
