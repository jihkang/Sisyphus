# Brief

## Task

- Task ID: `TF-20260421-feature-normalize-task-state-projections`
- Type: `feature`
- Slug: `normalize-task-state-projections`
- Branch: `feat/normalize-task-state-projections`

## Problem

- Normalize task state projections
- Original request: Follow up from umbrella issue TF-20260420-issue-assess-third-party-critique-of-sisyphus-codebase and the adaptive planning design-layer work. Unify plan/spec/design/conformance/MCP projections through one normalization path so task.json, PLAN/FIX_PLAN parsing, CLI status, service notifications, artifact projection, and MCP resources stop disagreeing about task state.

## Desired Outcome

- Loading, listing, and saving task records all pass through the same docs-derived normalization path.
- MCP `task://.../record`, API/CLI task listings, and lifecycle code see the same `test_strategy` and `design` projection for a task.
- Doc-synced projection state is available without relying on only a few planning/audit call sites to hydrate it first.

## Acceptance Criteria

- [x] `load_task_record`, `list_task_records`, and `save_task_record` share one normalization path for doc-derived state.
- [x] PLAN/FIX_PLAN-derived `test_strategy` and `design` state show up in normal task loads and MCP record resources without extra manual sync steps.
- [x] Focused and broader regression suites pass after the projection-path change.
- [x] Task docs record the implemented scope and verification coverage.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
