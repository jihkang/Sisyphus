# Brief

## Task

- Task ID: `TF-20260614-feature-wire-episode-trace-capture`
- Type: `feature`
- Slug: `wire-episode-trace-capture`
- Branch: `feat/wire-episode-trace-capture`

## Problem

- Sisyphus already has an `EpisodeStep` primitive, but MCP lifecycle/action calls are not automatically recorded.
- Agent debugging needs a durable record of the observation hash, selected action, result, and state transition for each task-scoped MCP mutation.

Scope:
- Record MCP call_tool actions with state_before, observation hash, action name/arguments, result, state_after, and state_diff.
- Optionally record resource reads for observation and task-critical resources without capturing chain-of-thought or private reasoning.
- Add episode id selection/generation policy and write JSONL under .planning/tasks/<task-id>/artifacts/episodes/.
- Add a replay/check command or read-only API that validates trace shape and can summarize action sequences.
- Keep trace writes atomic enough to avoid corrupt JSONL lines.

Acceptance criteria:
- A verify_task MCP call produces an episode JSONL step.
- A forbidden action attempt is traceable with gates/result.
- Observation hash in the trace matches the rendered observation snapshot.
- Trace schema tests and MCP integration tests pass.

Dependency: should follow lifecycle/action boundary enforcement or use its current registry interfaces.

## Desired Outcome

- Task-scoped MCP mutation calls write episode JSONL records under `.planning/tasks/<task-id>/artifacts/episodes/`.
- A read-only CLI check can validate trace shape and summarize action sequences.
- No chain-of-thought or private reasoning is captured; traces store state/action/result/evidence only.

## Acceptance Criteria

- [x] `sisyphus.verify_task` MCP calls produce episode trace steps.
- [x] Blocked lifecycle attempts are traceable with gates and state diffs.
- [x] Trace records include the pre-action observation hash.
- [x] Trace validation/read API is covered by tests.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Keep test-first agent execution loop work as a follow-up TODO; this task only captures episode traces.
