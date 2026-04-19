# Brief

## Task

- Task ID: `TF-20260419-feature-refactor-shared-generic-helpers-into-utils-package`
- Type: `feature`
- Slug: `refactor-shared-generic-helpers-into-utils-package`
- Branch: `feat/refactor-shared-generic-helpers-into-utils-package`

## Problem

- Refactor shared generic helpers into utils package
- Original request: Refactor shared generic helpers into a structured sisyphus utils package. Extract clearly reusable coercion and mapping helpers from live modules such as mcp_core and evolution.dataset into src/sisyphus/utils/, convert callers to import them, and keep domain-specific artifact/evolution policy helpers in their local modules. Add regression coverage for the shared utils behavior and for the touched modules so the refactor is behavior-preserving. Do not broaden scope into promotion logic or artifact policy evaluation.

## Desired Outcome

- The repository behavior matches the requested conversation outcome.
- The resulting change stays scoped to this task branch and worktree.

## Acceptance Criteria

- [ ] `src/sisyphus/utils/` becomes a real package and remains the home for generic helper code, while public imports used by existing callers stay stable.
- [ ] Clearly reusable helper functions are extracted from live modules such as `sisyphus.mcp_core` and `sisyphus.evolution.dataset` into shared utility modules instead of staying duplicated as local private helpers.
- [ ] Domain-specific artifact and evolution policy helpers are left in their local modules and are not misclassified as generic utilities.
- [ ] Regression tests cover the shared helper behavior and the touched live modules so the refactor is behavior-preserving.
- [ ] Task docs and verification notes reflect the final helper boundaries and verification scope.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Keep scope to generic helper extraction and import cleanup; do not broaden into promotion logic, artifact policy evaluation, or MCP contract changes.
