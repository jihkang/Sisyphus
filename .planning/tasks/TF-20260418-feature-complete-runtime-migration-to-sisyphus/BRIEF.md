# Brief

## Task

- Task ID: `TF-20260418-feature-complete-runtime-migration-to-sisyphus`
- Type: `feature`
- Slug: `complete-runtime-migration-to-sisyphus`
- Branch: `feat/complete-runtime-migration-to-sisyphus`

## Problem

- The repository had reached a dual-package state where `sisyphus` exposed the canonical names, but significant runtime ownership still lived under `taskflow`.
- The migration needed to be executed in safe slices so `sisyphus` became the real implementation root without breaking legacy imports, launchers, `.taskflow.toml` fallback behavior, or persisted protocol identifiers.
- This umbrella task tracks the full staged runtime migration rather than a single file move.

## Desired Outcome

- Core runtime modules, MCP surfaces, evolution modules, and the CLI are all canonically implemented under `src/sisyphus`.
- `taskflow` remains a supported legacy namespace through compatibility aliasing and wrappers instead of acting as the implementation authority.
- Focused regression coverage proves that canonical and legacy module paths remain compatible.
- The staged migration path is recorded explicitly through closed slice tasks and task docs.

## Acceptance Criteria

- [x] `TF-20260418-feature-migrate-core-runtime-modules-to-sisyphus` completed and closed.
- [x] `TF-20260418-feature-migrate-evolution-and-mcp-modules-to-sisyphus` completed and closed.
- [x] `TF-20260418-feature-invert-taskflow-into-compatibility-shims` completed and closed.
- [x] Canonical `sisyphus` ownership now covers core runtime, MCP, evolution, and CLI surfaces.
- [x] Legacy `taskflow` compatibility remains intact and validated with focused regression coverage.

## Constraints

- Preserve `.taskflow.toml` fallback behavior and persisted protocol identifiers unless a later task explicitly changes them.
- Keep the migration staged and compatibility-safe instead of forcing a flag-day removal of `taskflow`.
- Re-read the task docs before verify and close.
