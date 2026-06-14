# Plan

## Implementation Plan

1. [x] Extend `episode_trace.py` with deterministic episode id selection, next-step calculation, JSONL read/check helpers, and JSON-safe step serialization.
2. [x] Wrap task-scoped MCP mutation tools so they record state before, the pre-action observation hash, action name/arguments, result, state after, and state diff.
3. [x] Add a read-only `sisyphus episode check <task-id>` command that validates trace shape and summarizes action sequences.
4. [x] Add regression tests for successful `verify_task` traces, blocked lifecycle attempts with gates, and trace shape checking.
5. [x] Defer the separate test-first execution loop to the eval/loop task, where it can be modeled as an explicit red-green harness phase.

## Risks

- Trace capture writes task artifacts during MCP mutation calls, so failures should be surfaced by tests.
- State snapshots can be large if future task records grow; this task keeps tracing scoped to task-local lifecycle actions.
- The test-first loop is intentionally not implemented here because it changes the agent execution policy, not just trace capture.

## Design Evaluation

- Design Mode: `none`
- Decision Reason: `existing contract only`
- Confidence: `medium`
- Layer Impact: `layer-preserving`
- Layer Decision Reason: `n/a`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `n/a`

## Test Strategy

### Normal Cases

- [x] A successful `sisyphus.verify_task` MCP call writes one episode JSONL step.

### Edge Cases

- [x] A blocked `sisyphus.verify_task` attempt records lifecycle gates and the failed state transition.

### Exception Cases

- [x] Trace shape validation reports malformed or incomplete episode records clearly.

## Verification Mapping

- `A successful sisyphus.verify_task MCP call writes one episode JSONL step` -> `tests.test_mcp_core`
- `A blocked sisyphus.verify_task attempt records lifecycle gates and the failed state transition` -> `tests.test_mcp_core`
- `Trace shape validation reports malformed or incomplete episode records clearly` -> `tests.test_episode_trace`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`

## Deferred TODO

- Add an explicit test-first loop before implementation in the eval/agent-loop work: generate or select verification tests, observe the failing baseline, implement, rerun, and trace the red-green transition as first-class episode steps.
