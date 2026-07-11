# Brief

## Task

- Task ID: `TF-20260711-feature-harden-inbox-events-and-split-daemon-boundaries`
- Type: `feature`
- Slug: `harden-inbox-events-and-split-daemon-boundaries`
- Branch: `feat/harden-inbox-events-and-split-daemon-boundaries`

## Problem

- Harden inbox events and split daemon boundaries
- Original request: Implement the next repository-review remediation as one compatibility-preserving change. Introduce strict typed inbox event and payload models with explicit allow-lists, exact scalar/container type checks, bounded strings and collections, non-negative/positive integer constraints, safe relative changed-file paths, and JSON-serializable source_context. Move inbox persistence/claim/complete/fail mechanics behind an infra repository using existing atomic JSON persistence. Make malformed JSON, malformed schema, and unsupported event types isolated failures that are moved to the failed inbox, logged, counted, and never crash the daemon cycle or remain pending. Extract task brief/plan rendering from daemon.py into a domain task document module while preserving all existing daemon imports as compatibility aliases. Preserve the current public dict-shaped queue/process API and all valid-event behavior. Add focused unit tests for valid events, rejection classes, failure quarantine, atomic queue writes, continuation after a bad event, compatibility imports, and unchanged valid outputs. Run the full test suite, branch coverage gate, lock check, package build, Sisyphus verification, CI, PR, merge receipt, and close.

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
