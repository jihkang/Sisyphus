# Plan

## Implementation Plan

1. Read the repo MCP schema and status resources first: `repo://schema/mcp`, `repo://status/board`, `repo://status/conformance`, and `repo://status/events`.
2. Cross-check the MCP findings against the core self-evolution plan, current evolution code/tests, `AGENTS.md`, `README.md`, and `init-mcp.sh`.
3. Record the next concrete self-evolution work items exposed by that inspection and complete the feasible slices through normal Sisyphus task execution.
4. Update the task docs so this umbrella task reflects the inspection evidence and the concrete follow-up tasks it unblocked.

## Risks

- The discovery task can become redundant once the follow-up slices are split out, so the final record must point to those concrete tasks explicitly.
- MCP inspection is only useful if the resulting work is actually executed; otherwise the task would stop at analysis instead of producing outcome-bearing follow-up slices.

## Test Strategy

### Normal Cases

- [x] Repo MCP resources and local docs are sufficient to identify the current control-plane architecture and the remaining self-evolution slices.
- [x] The concrete feasible slices discovered from that inspection are executed end-to-end as separate Sisyphus tasks.

### Edge Cases

- [x] The repository board remains green while the exploration task fans out into smaller implementation tasks that can be verified independently.

### Exception Cases

- [x] Duplicate or superseded task creation attempts are visible in the event feed and do not prevent the next valid follow-up tasks from being created and completed.

## Verification Mapping

- `MCP resources and local docs identify the current architecture` -> `manual review of repo://schema/mcp, repo://status/board, repo://status/conformance, repo://status/events, README.md, init-mcp.sh`
- `Feasible follow-up slices are executed end-to-end` -> `./.venv/bin/python -m unittest tests.test_evolution -v` plus closed follow-up tasks for evolution core/dataset/harness/constraints/report`
- `Duplicate task creation is visible and recoverable` -> `manual review of repo://status/events`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
