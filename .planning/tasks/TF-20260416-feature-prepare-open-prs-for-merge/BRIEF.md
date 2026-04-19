# Brief

## Task

- Task ID: `TF-20260416-feature-prepare-open-prs-for-merge`
- Type: `feature`
- Slug: `prepare-open-prs-for-merge`
- Branch: `feat/prepare-open-prs-for-merge`

## Problem

- Prepare the two open GitHub pull requests for safe merge without disturbing unrelated dirty changes in the repository root.
- Original request: merge PR #9 into `main` first, then reconcile the stacked PR #10 against the updated base, resolve real conflicts, validate the merged result, and record the outcome in Sisyphus task docs.

## Desired Outcome

- PR #9 and PR #10 are both merged with the intended behavior preserved.
- Overlapping lifecycle files keep both the task-record locking changes and the `sisyphus` naming compatibility work.
- Merge work stays isolated to the task worktree so unrelated dirty state in the root repository is not mixed into the merge path.

## Acceptance Criteria

- [x] PR #9 is merged into `main`.
- [x] PR #10 is reconciled on top of the post-PR-#9 base, conflicts are resolved, and the result is merged.
- [x] Task docs and verification notes reflect the actual merge and validation work.

## Constraints

- Preserve existing repository conventions unless the merge reconciliation requires a deliberate compatibility fix.
- Keep merge and conflict-resolution work inside the isolated task worktree because the repository root is already dirty.
- Re-read the task docs before verify and close.
