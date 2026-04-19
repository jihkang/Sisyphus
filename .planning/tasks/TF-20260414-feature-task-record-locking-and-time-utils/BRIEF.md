# Brief

## Task

- Task ID: `TF-20260414-feature-task-record-locking-and-time-utils`
- Type: `feature`
- Slug: `task-record-locking-and-time-utils`
- Branch: `feat/task-record-locking-and-time-utils`

## Problem

- Task record locking and shared time utils
- Original request: Implement task record locking and timestamp helper consolidation. Add cross-process-safe task.json writes with a repository-local lock or equivalent atomic guard around read-modify-write flows, and consolidate duplicated utc_now() helpers into a shared utility used by state, events, conformance, and evolution modules. Keep scope to the persistence/timestamp layer plus regression coverage.

## Desired Outcome

- The repository behavior matches the requested conversation outcome.
- The resulting change stays scoped to this task branch and worktree.

## Acceptance Criteria

- [ ] `taskflow.utils` exposes the shared `utc_now()` helper and duplicated local implementations are removed from `state`, `events`, `conformance`, and `evolution/*`.
- [ ] Task record mutations use a repository-local lock plus atomic write path so read-modify-write flows do not interleave across daemon, planning, workflow, audit, and closeout updates.
- [ ] Regression tests and verify notes cover both the shared timestamp helper behavior and the locked task record update path.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
