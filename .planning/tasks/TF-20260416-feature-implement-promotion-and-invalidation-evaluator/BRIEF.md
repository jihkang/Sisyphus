# Brief

## Task

- Task ID: `TF-20260416-feature-implement-promotion-and-invalidation-evaluator`
- Type: `feature`
- Slug: `implement-promotion-and-invalidation-evaluator`
- Branch: `feat/implement-promotion-and-invalidation-evaluator`

## Problem

- implement promotion and invalidation evaluator
- Original request: Implement PromotionDecision and InvalidationRecord models plus evaluator helpers for FeatureChangeArtifact. The slice should compute candidate, verified, promotable, stale, and invalid states from slot bindings, verification claims, lineage, approvals, and invariant checks. Keep scope to policy evaluation and tests, not full workflow integration or live mutation routing.

## Desired Outcome

- The repository behavior matches the requested conversation outcome.
- The resulting change stays scoped to this task branch and worktree.

## Acceptance Criteria

- [ ] The requested workflow is implemented or corrected.
- [ ] The task docs reflect the actual implementation and verification scope.
- [ ] Verification notes are ready to be updated after implementation.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
