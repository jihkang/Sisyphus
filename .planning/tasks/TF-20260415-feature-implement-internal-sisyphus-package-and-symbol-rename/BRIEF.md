# Brief

## Task

- Task ID: `TF-20260415-feature-implement-internal-sisyphus-package-and-symbol-rename`
- Type: `feature`
- Slug: `implement-internal-sisyphus-package-and-symbol-rename`
- Branch: `feat/implement-internal-sisyphus-package-and-symbol-rename`

## Problem

- Internal code and tests still use `taskflow` heavily even after the canonical CLI/MCP entrypoint and config work.
- The next slice should make `sisyphus.<submodule>` the canonical import surface and rename obvious internal symbols, while leaving `taskflow` in place as a compatibility package.
- Protocol and persisted identifiers remain out of scope.

## Desired Outcome

- Canonical imports such as `sisyphus.config`, `sisyphus.daemon`, `sisyphus.provider_wrapper`, and `sisyphus.evolution` work across the codebase.
- Core internal symbol names prefer `Sisyphus*` over `Taskflow*`, with compatibility aliases preserved where needed.
- Tests and wrappers prefer canonical `sisyphus` imports where practical.
- `taskflow` remains a working compatibility package.

## Acceptance Criteria

- [ ] `sisyphus.<submodule>` aliases exist for the main internal modules and the evolution package.
- [ ] `SisyphusConfig` becomes the canonical internal config type name, with `TaskflowConfig` preserved as an alias.
- [ ] Obvious internal helper and docstring names no longer prefer `taskflow`.
- [ ] Tests and wrapper entrypoints use canonical `sisyphus` imports where the runtime now supports them.
- [ ] Regression tests cover canonical module aliases and renamed internal symbols without breaking `taskflow` compatibility.

## Constraints

- Preserve `taskflow` compatibility for existing imports and scripts.
- Do not rename `taskflow.event.v1`, `TF-...` task ids, or remove `.taskflow.toml` fallback support in this slice.
- Keep physical source paths such as `src/taskflow/...` out of scope unless a change is strictly required.
- Re-read the task docs before verify and close.
