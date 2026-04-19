# Brief

## Task

- Task ID: `TF-20260419-feature-repair-sisyphus-task-creation-runtime-after-taskflow-removal`
- Type: `feature`
- Slug: `repair-sisyphus-task-creation-runtime-after-taskflow-removal`
- Branch: `feat/repair-sisyphus-task-creation-runtime-after-taskflow-removal`

## Problem

- `sisyphus.request_task` through the MCP runtime still fails with `No such file or directory: '/Users/jihokang/Documents/Sisyphus/src/taskflow/templates_data/feature'`.
- Direct CLI fallback can still create tasks, which indicates the repository source is mostly correct but the active task-creation runtime path is stale or partially migrated.
- The task creation path must resolve templates exclusively from `src/sisyphus/templates_data` after the taskflow removal.

## Desired Outcome

- `request_task` succeeds consistently through API, MCP, and CLI without referencing `src/taskflow/templates_data`.
- The active task creation/runtime call path is aligned on Sisyphus-owned template discovery.
- Regression coverage proves the runtime no longer falls back to taskflow template paths.

## Acceptance Criteria

- [x] MCP registration and direct task-creation runtime no longer rely on `src/taskflow/templates_data`, and the launcher pins MCP execution to the current `sisyphus` source tree.
- [x] The fix stays scoped to task creation/runtime/template resolution and does not broaden into unrelated lifecycle changes.
- [x] Regression tests cover the repaired path and would fail if taskflow template resolution reappears.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Keep scope limited to runtime/template resolution for task creation; do not fold in unrelated evolution or promotion work.
