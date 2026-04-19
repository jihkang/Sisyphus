# Brief

## Task

- Task ID: `TF-20260418-feature-remove-taskflow-compatibility-layer`
- Type: `feature`
- Slug: `remove-taskflow-compatibility-layer`
- Branch: `feat/remove-taskflow-compatibility-layer`

## Problem

- The runtime migration is complete, but the repository still carried a legacy `taskflow` package, console script, and compatibility-oriented test/doc references.
- Those remaining live references kept the old package visible even though `sisyphus` already owned the implementation.
- This task removes the live `taskflow` compatibility package and entrypoint, switches repo-local callers and docs to `sisyphus`, and preserves only explicitly intentional persisted compatibility such as `.taskflow.toml` fallback and `taskflow.event.v1`.

## Desired Outcome

- `src/taskflow/` is removed from the live source tree.
- The `taskflow` console script entrypoint is removed from packaging metadata.
- Repo-local code, tests, and live docs reference `sisyphus` as the only canonical Python package surface.
- Legacy persisted compatibility that is not part of the package alias layer remains intact where intentionally preserved.

## Acceptance Criteria

- [x] Live code no longer imports or aliases `taskflow` modules.
- [x] The `src/taskflow/` package is removed.
- [x] The `taskflow` console script entrypoint is removed from `pyproject.toml`.
- [x] Repo-local tests and live docs are updated to the canonical `sisyphus` package surface.
- [x] Focused regression coverage passes after the package removal.

## Constraints

- Preserve `.taskflow.toml` fallback support unless a separate task removes that persisted compatibility.
- Preserve `taskflow.event.v1` unless a separate task handles protocol/schema migration.
- Re-read the task docs before verify and close.
