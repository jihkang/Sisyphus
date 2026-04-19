# Brief

## Task

- Task ID: `TF-20260418-feature-migrate-evolution-and-mcp-modules-to-sisyphus`
- Type: `feature`
- Slug: `migrate-evolution-and-mcp-modules-to-sisyphus`
- Branch: `feat/migrate-evolution-and-mcp-modules-to-sisyphus`

## Problem

- The canonical names for MCP and self-evolution already point at `sisyphus`, but the implementation authority for `mcp_core`, `mcp_adapter`, `mcp_server`, and `evolution/*` still depended on `taskflow` modules and wrappers.
- That split leaves the self-hosted execution and evaluation surfaces only partially migrated, which makes the naming unification incomplete and keeps the runtime contract harder to reason about.
- This slice needs to move the MCP and evolution implementations into `src/sisyphus`, while preserving legacy `taskflow` imports as explicit compatibility paths.

## Desired Outcome

- `src/sisyphus/mcp_core.py`, `src/sisyphus/mcp_adapter.py`, and `src/sisyphus/mcp_server.py` own the MCP implementation.
- `src/sisyphus/evolution/*` owns the evolution implementation surface.
- Legacy imports such as `taskflow.mcp_server` and `taskflow.evolution.constraints` continue to resolve to the canonical `sisyphus` implementations.
- MCP tool names, resource URIs, and evolution behavior remain unchanged while the package ownership moves.

## Acceptance Criteria

- [x] MCP implementation modules are copied into `src/sisyphus` and no longer rely on `taskflow` aliasing from the canonical package.
- [x] Evolution implementation modules are copied into `src/sisyphus/evolution`.
- [x] Legacy `taskflow` MCP and evolution imports resolve to canonical `sisyphus` implementations through compatibility aliasing or wrappers.
- [x] Focused regression coverage validates both canonical imports and legacy compatibility imports.
- [x] Read/write behavior, MCP tool names, and resource URI semantics remain unchanged.

## Constraints

- Keep the canonical MCP namespace as `sisyphus.*`; this task is about ownership migration, not protocol renaming.
- Preserve legacy `taskflow` import compatibility while the migration is in progress.
- Re-read the task docs before verify and close.
