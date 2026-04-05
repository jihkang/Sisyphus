# Brief

## Task

- Task ID: `TF-20260402-feature-spec-check-task`
- Type: `feature`
- Slug: `spec-check-task`
- Branch: `feat/spec-check-task`

## Problem

- `taskflow new` currently writes metadata and template files only.
- The CLI prints a branch name and worktree path, but it does not actually create a branch or a git worktree.
- This mismatch makes the generated task record look actionable even though a developer still has to manually run git setup outside the tool.

## Desired Outcome

- `taskflow new feature <slug>` and `taskflow new issue <slug>` should create a usable task workspace, not just a plan record.
- After creation, the requested branch should exist from the configured base branch and the configured worktree path should be materialized on disk.
- Failure cases should leave a clear error and avoid half-created task state that suggests success.

## Acceptance Criteria

- [x] `taskflow new` creates the task record, materializes task docs, creates the branch, and creates the worktree in one flow.
- [x] If the branch already exists or the target worktree path already exists, the command fails with a clear error and does not leave a misleading partial task record behind.
- [x] The created branch starts from `base_branch` in `.taskflow.toml` or the default `main` when no config is present.
- [x] The stored `branch`, `base_branch`, and `worktree_path` metadata match the real git objects that were created.

## Constraints

- Keep scope limited to create-time git setup; do not implement worktree removal in this task.
- Preserve the current spec-first verify flow and existing task document structure.
