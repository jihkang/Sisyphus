# Brief

## Task

- Task ID: `TF-20260421-feature-parent-merge-retarget-and-reverify`
- Type: `feature`
- Slug: `parent-merge-retarget-and-reverify`
- Branch: `feat/parent-merge-retarget-and-reverify`

## Problem

- Retarget and reverify child promotion after parent merge
- Original request: Follow up from umbrella issue TF-20260420-issue-assess-third-party-critique-of-sisyphus-codebase. When a parent stacked PR merges, detect impacted child promotions, recompute base/lineage, and require retarget/rebase plus re-verify before further promotion. First version may be detect plus gate plus operator action rather than fully automatic mutation.

## Desired Outcome

- The repository behavior matches the requested conversation outcome.
- The resulting change stays scoped to this task branch and worktree.

## Acceptance Criteria

- [x] The requested workflow is implemented or corrected.
- [x] The task docs reflect the actual implementation and verification scope.
- [x] Verification notes are ready to be updated after implementation.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
