# Plan

## Implementation Plan

1. Add git operation helpers for branch existence checks, branch creation from the configured base branch, and worktree creation at the computed target path.
2. Update `taskflow.cli handle_new` flow so task creation only reports success after git setup and template materialization both succeed.
3. Define rollback behavior for partial failures so branch/worktree setup errors do not leave task metadata that falsely implies a ready workspace.
4. Extend tests to cover successful create flow and duplicate branch or preexisting worktree failures.

## Risks

- Git commands may behave differently when the configured base branch does not exist locally or only exists on the remote.
- A partially created branch or worktree can leave the repository in an ambiguous state if the command fails after writing `task.json`.
- Existing task fixtures store absolute paths from older environments, so path resolution must remain resilient across platforms.

## Test Strategy

### Normal Cases

- [ ] Creating a feature task from a clean repository creates the expected branch, worktree directory, task record, and template files.
- [ ] Creating an issue task uses the issue branch prefix and still provisions the branch from the configured base branch.

### Edge Cases

- [ ] A repository without `.taskflow.toml` still creates the branch from `main` and uses the default worktree root.
- [ ] A relative `worktree_root` in config resolves correctly from the repository root and is stored consistently in task metadata.

### Exception Cases

- [ ] If the target branch already exists, `taskflow new` exits with a failure and does not leave a misleading new task directory behind.
- [ ] If the target worktree path already exists, `taskflow new` exits with a failure and does not report success.
- [ ] If git setup partially succeeds and a later step fails, rollback leaves the repository in a deterministic state that can be retried manually.

## Verification Mapping

- `Creating a feature task from a clean repository creates the expected branch, worktree directory, task record, and template files.` -> `integration_test`
- `Creating an issue task uses the issue branch prefix and still provisions the branch from the configured base branch.` -> `integration_test`
- `A repository without .taskflow.toml still creates the branch from main and uses the default worktree root.` -> `integration_test`
- `A relative worktree_root in config resolves correctly from the repository root and is stored consistently in task metadata.` -> `unit_test`
- `If the target branch already exists, taskflow new exits with a failure and does not leave a misleading new task directory behind.` -> `integration_test`
- `If the target worktree path already exists, taskflow new exits with a failure and does not report success.` -> `integration_test`
- `If git setup partially succeeds and a later step fails, rollback leaves the repository in a deterministic state that can be retried manually.` -> `manual_check`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
