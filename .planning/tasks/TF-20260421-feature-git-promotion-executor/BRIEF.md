# Brief

## Task

- Task ID: `TF-20260421-feature-git-promotion-executor`
- Type: `feature`
- Slug: `git-promotion-executor`
- Branch: `feat/git-promotion-executor`

## Problem

- Add git promotion executor
- Original request: Follow up from umbrella issue TF-20260420-issue-assess-third-party-critique-of-sisyphus-codebase. Implement the promotion executor that materializes commit, push, and PR-open actions for promotable changes. Current gitops only provisions branch/worktree, so this task should define and implement the actual promotion execution chain and its receipts.

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
