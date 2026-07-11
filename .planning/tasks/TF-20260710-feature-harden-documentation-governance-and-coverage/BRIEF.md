# Brief

## Task

- Task ID: `TF-20260710-feature-harden-documentation-governance-and-coverage`
- Type: `feature`
- Slug: `harden-documentation-governance-and-coverage`
- Branch: `feat/harden-documentation-governance-and-coverage`

## Problem

- Harden documentation governance and coverage
- Original request: Implement the remaining low-risk operational hardening from the repository review. Update docs/architecture.md so it describes the current compat/interface/domain/infra/shared structure and implemented evolution/observation surfaces; add contributor and release-policy documentation; add reproducible coverage collection to the locked CI flow without weakening the existing Python 3.11-3.14 test and package gates; update README links and commands. Preserve runtime behavior. LICENSE text is conditional on an explicit operator license choice and must not be guessed.

## Desired Outcome

- The repository behavior matches the requested conversation outcome.
- The resulting change stays scoped to this task branch and worktree.

## Acceptance Criteria

- [ ] The requested workflow is implemented or corrected.
- [ ] The task docs reflect the actual implementation and verification scope.
- [ ] Verification notes are ready to be updated after implementation.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
