# Plan

## Implementation Plan

1. Confirm the actual provisioning path by tracing `creation.py` and `gitops.py`, then capture the rule that new task worktrees start from `config.base_branch`.
2. Validate that the realignment task adopted the current root dirty snapshot and record the adopted baseline in task docs.
3. Compare active non-closed task branches against the current root baseline to determine whether any branch contains unique commits that must be preserved before superseding its worktree.
4. Document the operating rule in repository architecture docs:
   - root dirty state is not implicitly present in a new task worktree
   - `adopt_current_changes` overlays the current root snapshot into the new task worktree
   - when root becomes the authoritative source of truth, further implementation must continue from a freshly adopted baseline rather than stale task worktrees
5. Record which current task worktrees are superseded, which must be replayed on the adopted baseline, and which can remain archival only.

## Risks

- A branch could still hold unique committed work even if its worktree is stale; classification must distinguish branch divergence from uncommitted root drift.
- Over-documenting task-specific branch names in permanent repository docs would create stale architecture text; task-local findings should stay in this task log.

## Test Strategy

### Normal Cases

- [ ] The realignment task shows adopted root changes and points at the intended source branch.
- [ ] Repository docs describe the base-branch provisioning rule and the direct-change adoption escape hatch.

### Edge Cases

- [ ] A task branch that is behind the root baseline but not ahead is classified as superseded without requiring cherry-pick.
- [ ] A task branch that matches the root commit but lacks the root dirty snapshot is still treated as stale for ongoing implementation.

### Exception Cases

- [ ] If a task branch is found to be ahead of the root baseline, the log explicitly marks it as requiring replay or cherry-pick instead of superseding it silently.

## Verification Mapping

- `The realignment task shows adopted root changes and points at the intended source branch.` -> `read task://.../record and inspect adopted_changes metadata`
- `Repository docs describe the base-branch provisioning rule and the direct-change adoption escape hatch.` -> `manual review of docs/architecture.md`
- `A task branch that is behind the root baseline but not ahead is classified as superseded without requiring cherry-pick.` -> `git rev-list --left-right --count <root-head>...<branch>`
- `A task branch that matches the root commit but lacks the root dirty snapshot is still treated as stale for ongoing implementation.` -> `compare active worktree heads plus adopted-baseline notes`
- `If a task branch is found to be ahead of the root baseline, the log explicitly marks it as requiring replay or cherry-pick instead of superseding it silently.` -> `manual review of classification log`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
