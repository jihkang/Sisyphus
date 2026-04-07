# Brief

## Task

- Task ID: `TF-20260407-feature-direct-change-adoption`
- Type: `feature`
- Slug: `direct-change-adoption`
- Branch: `feat/direct-change-adoption`

## Problem

- Add direct-change adoption so existing local edits can be attached to a formal task with traceable provenance.
- Starting work directly in the repo root leaks context because the task branch and task worktree begin from a clean base and do not automatically capture those edits.
- The system needs an explicit way to carry current local changes into a new task while recording where they came from.

## Desired Outcome

- `taskflow request` and `taskflow ingest conversation` can adopt current local changes into the newly created task worktree.
- The task record preserves adoption provenance such as source branch, requested paths, and adopted file list.
- The feature stays inspectable through task metadata and task log notes.

## Acceptance Criteria

- [x] Conversation requests accept direct-change adoption options for current local edits.
- [x] Inbox processing copies requested dirty files into the new task worktree and removes adopted deletions.
- [x] Task metadata records adoption provenance and task logs note the adoption event.
- [x] Regression tests cover parser handling, inbox adoption behavior, and request output.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Exclude internal `.planning` metadata from adoption so taskflow does not adopt its own bookkeeping files.
