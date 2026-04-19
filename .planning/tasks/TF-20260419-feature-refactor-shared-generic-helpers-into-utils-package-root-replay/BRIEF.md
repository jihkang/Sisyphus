# Brief

## Task

- Task ID: `TF-20260419-feature-refactor-shared-generic-helpers-into-utils-package-root-replay`
- Type: `feature`
- Slug: `refactor-shared-generic-helpers-into-utils-package-root-replay`
- Branch: `feat/refactor-shared-generic-helpers-into-utils-package-root-replay`

## Problem

- `TF-20260419-feature-refactor-shared-generic-helpers-into-utils-package` already defined and verified the helper-refactor slice, but that task is blocked only because its stale task worktree predates the current root source-of-truth.
- The current root worktree now carries the active `taskflow` -> `sisyphus` migration baseline, so the utils refactor must be replayed on top of that adopted baseline rather than resumed in the old worktree.
- This follow-up task must preserve the original narrow boundary: generic helper extraction, utils package conversion, and behavior-preserving regression coverage only.

## Desired Outcome

- The repository behavior matches the requested conversation outcome on top of the current root-adopted baseline.
- `src/sisyphus/utils/` is the home for generic helper code while import ergonomics remain stable.
- Domain-specific artifact and evolution policy helpers stay in their local modules.

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
