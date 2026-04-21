# Brief

## Task

- Task ID: `TF-20260421-feature-promotable-change-classification`
- Type: `feature`
- Slug: `promotable-change-classification`
- Branch: `feat/promotable-change-classification`

## Problem

- Classify promotable changes
- Original request: Follow up from umbrella issue TF-20260420-issue-assess-third-party-critique-of-sisyphus-codebase. Add classification rules for which tasks or artifacts require promotion. MVP contract: repo-changing feature tasks are promotable by default, receipt/test/verification-only artifacts are not, and operator override remains possible.

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
