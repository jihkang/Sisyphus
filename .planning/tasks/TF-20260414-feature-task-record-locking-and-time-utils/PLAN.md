# Plan

## Implementation Plan

1. Add a shared `utc_now()` helper in `taskflow.utils`, then replace duplicated implementations in `state`, `events`, `conformance`, and `taskflow.evolution`.
2. Introduce a task-record update primitive that serializes read-modify-write with a repository-local lock and atomic replace, while keeping support-file sync behavior intact.
3. Refactor task-record write call sites that currently do `load -> mutate -> save` so they use the locked update path for planning, workflow, daemon, audit, closeout, and related lifecycle transitions.
4. Add regression coverage for timestamp formatting and locked task-record persistence, then update verify notes with the executed commands.

## Risks

- Lock scope must cover the full mutation window; a write-only lock would still allow lost updates.
- Task support files are mirrored into worktrees after saves, so the new write path must not break sync timing or leave stale copies behind.
- Existing direct `task.json` writes in tests or helper code may bypass the new primitive and need targeted cleanup.

## Test Strategy

### Normal Cases

- [ ] Lifecycle transitions that mutate `task.json` persist through the locked update path without dropping fields or conformance metadata.
- [ ] Shared `utc_now()` still returns UTC timestamps with a trailing `Z` for state, event, conformance, and evolution records.

### Edge Cases

- [ ] Support-file sync still updates the worktree copy of `task.json` and task docs after a locked save.
- [ ] Sequential updates preserve task defaults and nested `conformance` structures when existing records are partially populated.

### Exception Cases

- [ ] If a locked mutation callback raises, the original `task.json` remains readable and no partial write is left behind.

## Verification Mapping

- `Lifecycle transitions that mutate task.json persist through the locked update path without dropping fields or conformance metadata.` -> `python -m unittest tests.test_taskflow -v`
- `Shared utc_now() still returns UTC timestamps with a trailing Z for state, event, conformance, and evolution records.` -> `python -m unittest tests.test_taskflow tests.test_evolution -v`
- `Support-file sync still updates the worktree copy of task.json and task docs after a locked save.` -> `python -m unittest tests.test_taskflow -v`
- `Sequential updates preserve task defaults and nested conformance structures when existing records are partially populated.` -> `python -m unittest tests.test_taskflow -v`
- `If a locked mutation callback raises, the original task.json remains readable and no partial write is left behind.` -> `python -m unittest tests.test_taskflow -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
