# Plan

## Implementation Plan

1. Inspect the live MCP bootstrap path, launcher registration, and active Python import resolution to identify why `sisyphus.request_task` still resolves `src/taskflow/templates_data`.
2. Patch the MCP startup path so the live server imports the repository's canonical `sisyphus` package consistently after reconnect.
3. Add regression coverage around the failing bootstrap/import path and keep task creation behavior unchanged apart from the template resolution fix.
4. Reconnect or re-exercise the live MCP runtime, then verify the repaired `sisyphus.request_task` flow directly.

## Risks

- The stale path may come from an already-running MCP process rather than the launcher config alone.
- The `.venv` may contain an older installed package that shadows the repo source when the server starts.
- A narrow fix in the launcher can still miss direct entrypoints if the import precedence is not centralized.

## Test Strategy

### Normal Cases

- [ ] Live MCP `sisyphus.request_task` succeeds in the root repository after reconnect.
- [ ] CLI fallback task creation still works after the bootstrap change.

### Edge Cases

- [ ] MCP startup still prefers repo `src/` over stale installed packages when both exist.
- [ ] Reconnect path keeps using `sisyphus/templates_data` without requiring `taskflow` compatibility aliases.

### Exception Cases

- [ ] Startup failures surface an actionable runtime/bootstrap error instead of a misleading missing-template path.

## Verification Mapping

- `Live MCP sisyphus.request_task succeeds in the root repository after reconnect.` -> `direct MCP request_task probe`
- `CLI fallback task creation still works after the bootstrap change.` -> `targeted CLI request smoke test`
- `MCP startup still prefers repo src/ over stale installed packages when both exist.` -> `targeted regression test`
- `Startup failures surface an actionable runtime/bootstrap error instead of a misleading missing-template path.` -> `targeted regression test`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
