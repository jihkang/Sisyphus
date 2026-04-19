# Brief

## Task

- Task ID: `TF-20260418-feature-migrate-core-runtime-modules-to-sisyphus`
- Type: `feature`
- Slug: `migrate-core-runtime-modules-to-sisyphus`
- Branch: `feat/migrate-core-runtime-modules-to-sisyphus`

## Problem

- The repository still had two package roots, but the non-evolution runtime implementation mostly lived under `src/taskflow` while `src/sisyphus` remained a thin wrapper layer.
- That split blocks the naming unification work because canonical imports point at `sisyphus` while the real implementation authority still sits in `taskflow`.
- This slice needs to move the core runtime implementation into `src/sisyphus`, keep legacy `taskflow` imports working as compatibility aliases, and preserve compatibility-sensitive persisted identifiers.

## Desired Outcome

- `src/sisyphus` becomes the primary package for the non-evolution core runtime modules.
- Legacy `taskflow` imports for moved core modules continue to resolve to the same runtime behavior through compatibility aliasing.
- Template/resource loading works from the canonical `sisyphus` package data.
- Compatibility-sensitive persisted behavior remains intentional, including `.taskflow.toml` fallback reads and the `taskflow.event.v1` event schema identifier.

## Acceptance Criteria

- [x] Core non-evolution runtime modules and templates are copied into `src/sisyphus`.
- [x] `sisyphus.__init__` re-exports the library API from local `sisyphus` implementations instead of from `taskflow`.
- [x] `taskflow` core module imports resolve to moved `sisyphus` implementations through compatibility aliases.
- [x] Focused regression coverage validates the alias contract and targeted runtime/package behavior.
- [x] CLI, MCP, and evolution modules are explicitly deferred to follow-up migration slices instead of being partially moved in this change.

## Constraints

- Do not rename persisted compatibility identifiers just because the canonical package name changed.
- Preserve the current root branch work without reverting unrelated dirty files in the repository.
- Re-read the task docs before verify and close.
