# Plan

## Implementation Plan

1. Inspect the two open pull requests, confirm their base branches and overlap, and verify whether the stacked PR needs reconciliation after PR #9 lands.
2. Use an isolated task worktree to merge PR #9 into `main`, then merge PR #10 onto the updated base and resolve the overlapping lifecycle-module conflicts.
3. Validate the reconciled result, push the merge commit to the stacked base branch and `main`, and record the exact resolution and verification details in the task docs.

## Risks

- The repository root is currently dirty, so direct merge work must stay inside the dedicated task worktree to avoid mixing unrelated local changes into the PR branches.
- PR #10 is stacked on `feat/evolution-foundation` rather than `main`, so merging PR #9 first may still require a rebase or retarget step even if GitHub currently marks both PRs as mergeable.
- The two PRs overlap in lifecycle modules such as `audit.py`, `closeout.py`, `planning.py`, `workflow.py`, and `tests/test_taskflow.py`, so conflict resolution must be reviewed file by file instead of assuming automatic merge safety.

## Test Strategy

### Normal Cases

- [x] PR #9 merged cleanly into `main` and the updated `main` was pushed.
- [x] PR #10 was reconciled against the post-PR-#9 base and merged after conflict resolution.

### Edge Cases

- [x] Overlapping files in `audit.py`, `closeout.py`, `planning.py`, `workflow.py`, and `tests/test_taskflow.py` were resolved without dropping either the task-record locking behavior or the `sisyphus` naming compatibility work.
- [x] Local unrelated dirty files in the repository root remained untouched because merge work stayed in the isolated task worktree.

### Exception Cases

- [x] A post-merge regression in the close fixture was corrected by excluding internal `task.json.lock` files from dirty-worktree gating, and the branch remained recoverable throughout.

## Verification Mapping

- `PR #9 merges cleanly into main and the updated main is pushed.` -> `git merge --ff-only origin/feat/task-record-locking-and-time-utils and git push origin HEAD:main`
- `PR #10 is reconciled against the post-PR-#9 base and remains mergeable after conflict resolution.` -> `manual conflict review plus git commit and push of merge commit 48d9ee4`
- `Overlapping files that changed in both PRs are resolved without dropping either behavior set.` -> `targeted review of audit/closeout/planning/workflow/test_taskflow merge results`
- `Local unrelated dirty files in the repository root remain untouched because merge work happens only in the isolated task worktree.` -> `manual review of root worktree status during merge`
- `A merge regression is corrected without leaving the branch unrecoverable.` -> `targeted close fixture rerun plus full unittest suite`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
