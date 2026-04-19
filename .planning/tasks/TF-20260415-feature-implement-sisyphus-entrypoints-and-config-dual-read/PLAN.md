# Plan

## Implementation Plan

1. Add canonical `sisyphus` module entrypoints.
   - Create `src/sisyphus/cli.py` and `src/sisyphus/mcp_server.py` as thin wrappers over the existing `taskflow` implementations.
   - Keep the wrappers explicit and executable with `python -m sisyphus.cli` and `python -m sisyphus.mcp_server`.
   - Re-export enough public functions for tests and tooling to use the canonical modules directly.

2. Move canonical console scripts to the new modules.
   - Update `pyproject.toml` so `sisyphus` resolves to `sisyphus.cli:main`.
   - Update `pyproject.toml` so `sisyphus-mcp` resolves to `sisyphus.mcp_server:main`.
   - Keep `taskflow = "taskflow.cli:main"` unchanged as the compatibility script.

3. Add dual-read config support.
   - Teach config loading to prefer `.sisyphus.toml`.
   - Continue to load `.taskflow.toml` when the new file is absent.
   - Make repo-root discovery recognize both filenames, with `.sisyphus.toml` taking precedence.

4. Update docs and wrappers to the new canonical path.
   - Change direct launcher examples from `taskflow.mcp_server` to `sisyphus.mcp_server`.
   - Update config documentation to present `.sisyphus.toml` as preferred and `.taskflow.toml` as legacy fallback.
   - Update `init-mcp.sh` and wrapper example files to emit the canonical module path.

5. Add regression coverage and verify.
   - Add tests for canonical `sisyphus` module entrypoints.
   - Add tests for `.sisyphus.toml` precedence and `.taskflow.toml` fallback.
   - Run targeted unittests covering parser/module aliasing, config loading, repo discovery, and MCP server resolution.

## Risks

- Missing or partial re-exports in `sisyphus` wrappers could break direct module use even if console scripts work.
- Changing launcher examples before the canonical modules exist would make docs inaccurate.
- Config precedence must be deterministic when both `.sisyphus.toml` and `.taskflow.toml` are present.

## Test Strategy

### Normal Cases

- [ ] Canonical `sisyphus` CLI and MCP module entrypoints resolve to working wrappers.
- [ ] A repository configured only with `.sisyphus.toml` loads expected settings and is discoverable as a repo root.

### Edge Cases

- [ ] When both config files are present, `.sisyphus.toml` wins deterministically.
- [ ] A repository that still has only `.taskflow.toml` continues to work without migration.

### Exception Cases

- [ ] This slice does not accidentally rename high-risk protocol or persisted identifiers such as `taskflow.event.v1` or `TF-...`.
- [ ] Direct launcher docs do not point to nonexistent module paths.

## Verification Mapping

- `Canonical sisyphus CLI and MCP module entrypoints resolve to working wrappers.` -> `python -m unittest tests.test_taskflow tests.test_mcp_server -v`
- `A repository configured only with .sisyphus.toml loads expected settings and is discoverable as a repo root.` -> `python -m unittest tests.test_event_bus tests.test_taskflow tests.test_mcp_server -v`
- `Config precedence and legacy fallback remain deterministic.` -> `python -m unittest tests.test_event_bus tests.test_taskflow tests.test_mcp_server -v`
- `High-risk identifiers are unchanged and docs point to real module paths.` -> `manual review of diff`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
