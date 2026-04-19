# Brief

## Task

- Task ID: `TF-20260419-feature-realign-active-work-to-root-source-of-truth`
- Type: `feature`
- Slug: `realign-active-work-to-root-source-of-truth`
- Branch: `feat/realign-active-work-to-root-source-of-truth`

## Problem

- `create_task_workspace()` provisions task worktrees from the configured `base_branch`, not from the root worktree's dirty state.
- The current root worktree on `feat/sisyphus-naming-unification` carries the authoritative in-progress `taskflow` -> `sisyphus` migration and related follow-up edits that many older task worktrees do not contain.
- Original request: Create a root-based realignment task that adopts the current root working tree changes into a fresh task worktree so ongoing implementation can continue from the actual sisyphus source-of-truth rather than stale base-branch snapshots. Keep scope to establishing the aligned worktree, documenting the operating rule, and identifying which older task worktrees should be superseded or replayed from this adopted baseline.

## Desired Outcome

- A fresh task worktree exists with the current root dirty snapshot adopted into it.
- The architecture docs explain when task worktrees come from `base_branch` and when direct-change adoption is required.
- Active non-closed task worktrees are classified as either superseded, replay-on-realigned-baseline, or archival-only without losing unique branch commits.

## Acceptance Criteria

- [ ] The realignment task records that the adopted worktree is the active execution baseline for current migration work.
- [ ] Repository docs describe the task worktree baseline rule and the role of direct-change adoption.
- [ ] The current active task branches are classified, and the classification shows whether any branch contains commits that are not already present on the root baseline.

## Constraints

- Do not rewrite or discard the user's root dirty state.
- Do not pretend that older task worktrees are safe just because their branch heads match or trail `main`.
- Re-read the task docs before verify and close.
