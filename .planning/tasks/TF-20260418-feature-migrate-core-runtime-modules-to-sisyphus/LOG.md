# Log

## Timeline

- 2026-04-18: Inspected the package split and confirmed that `src/taskflow` still held the primary non-evolution runtime implementation while `src/sisyphus` mostly exposed wrapper aliases.
- 2026-04-18: Copied the core runtime modules, `py.typed`, and template assets into `src/sisyphus`.
- 2026-04-18: Flipped import ownership so `sisyphus` re-exports local implementations and `taskflow` aliases moved core modules for compatibility.
- 2026-04-18: Updated package data and regression coverage for the `taskflow -> sisyphus` compatibility contract.
- 2026-04-18: Ran focused validation with the targeted unittest suite and a direct import smoke check.

## Notes

- Intentionally preserved `.taskflow.toml` as a legacy fallback in config loading.
- Intentionally preserved the `taskflow.event.v1` schema identifier because it is part of persisted event compatibility.
- Intentionally deferred CLI, MCP, and evolution module migration to follow-up tasks so this slice only owns the non-evolution core runtime move.

## Follow-ups

- Migrate `cli`, `mcp_server`, `mcp_core`, `mcp_adapter`, and `evolution/*` implementations into `src/sisyphus`.
- Replace the remaining physical `src/taskflow/*` implementation files with explicit compatibility shims once all migration slices land.
