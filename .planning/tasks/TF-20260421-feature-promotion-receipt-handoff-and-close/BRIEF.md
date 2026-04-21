# Brief

## Task

- Task ID: `TF-20260421-feature-promotion-receipt-handoff-and-close`
- Type: `feature`
- Slug: `promotion-receipt-handoff-and-close`
- Branch: `feat/promotion-receipt-handoff-and-close`

## Problem

- Connect promotion receipt handoff and close eligibility
- Original request: Follow up from umbrella issue TF-20260420-issue-assess-third-party-critique-of-sisyphus-codebase. Extend the existing merge receipt recorder so promotion_recorded becomes a real handoff point into close eligibility. The task should connect receipt recording, task promotion state, and final closeout instead of leaving merge evidence as a detached after-the-fact note.

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
