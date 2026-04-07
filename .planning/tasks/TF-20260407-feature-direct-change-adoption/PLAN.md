# Plan

## Implementation Plan

1. Extend the conversation request surface with `--adopt-current-changes` and `--adopt-path`, and pass those fields through the API and queued event payload.
2. Add git helpers to detect dirty and deleted paths in the current repo root and copy or remove those paths in the new task worktree.
3. Apply adoption during inbox processing after task creation, excluding `.planning` internals and recording provenance in task metadata.
4. Surface adoption results in request output and task logs so another operator can inspect what was adopted.
5. Add regression tests for parser support, daemon adoption behavior, and request output.

## Risks

- Dirty-path detection can accidentally include taskflow bookkeeping files if internal metadata is not filtered out.
- Adoption can misrepresent provenance if the source branch or adopted path list is not persisted with the task.
- Deleted files need explicit handling so the task worktree matches the adopted local state.

## Test Strategy

### Normal Cases

- [x] A request can adopt a modified tracked file into the new task worktree and record provenance

### Edge Cases

- [x] Adoption can be limited to specific requested paths and excludes unrelated dirty files
- [x] Internal `.planning` files are not adopted into the task worktree

### Exception Cases

- [x] Existing no-run and pending-review behavior remains stable after adding adoption flags

## Verification Mapping

- `A request can adopt a modified tracked file into the new task worktree and record provenance` -> `uv run python -m unittest tests.test_taskflow.TaskflowDaemonTests tests.test_taskflow.TaskflowNewTests -v`
- `Adoption can be limited to specific requested paths and excludes unrelated dirty files` -> `uv run python -m unittest tests.test_taskflow.TaskflowDaemonTests tests.test_taskflow.TaskflowNewTests -v`
- `Internal .planning files are not adopted into the task worktree` -> `uv run python -m unittest tests.test_taskflow.TaskflowDaemonTests tests.test_taskflow.TaskflowNewTests -v`
- `Existing no-run and pending-review behavior remains stable after adding adoption flags` -> `uv run python -m unittest tests.test_taskflow.TaskflowDaemonTests tests.test_taskflow.TaskflowNewTests -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
