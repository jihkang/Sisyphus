# Brief

## Task

- Task ID: `TF-20260710-feature-add-reproducible-lockfile-and-ci`
- Type: `feature`
- Slug: `add-reproducible-lockfile-and-ci`
- Branch: `feat/add-reproducible-lockfile-and-ci`

## Problem

- Add reproducible lockfile and CI quality gate
- Original request: Add the first operational-foundation improvement from the repository review: make dependency resolution reproducible by tracking a freshly generated uv.lock, remove the lockfile ignore rule, and add GitHub Actions CI that uses the frozen lock to install the project, runs the complete unittest suite, and verifies the package can be built. Keep this task narrowly scoped to lockfile/CI/docs; do not choose a license or refactor runtime behavior. Preserve Python 3.11+ support and existing CLI/MCP behavior.

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
