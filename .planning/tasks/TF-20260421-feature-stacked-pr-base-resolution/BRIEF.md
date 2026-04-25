# Brief

## Task

- Task ID: `TF-20260421-feature-stacked-pr-base-resolution`
- Type: `feature`
- Slug: `stacked-pr-base-resolution`
- Branch: `feat/stacked-pr-base-resolution`

## Problem

- Resolve stacked PR base from artifact lineage
- Original request: Follow up from umbrella issue TF-20260420-issue-assess-third-party-critique-of-sisyphus-codebase. Add promotion.strategy=direct|stacked and implement base-branch resolution from frozen explicit base, parent artifact/task lineage, and fallback base_branch rules. The output should explain why a PR used its chosen base and preserve that lineage for receipts.

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
