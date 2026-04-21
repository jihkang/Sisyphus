# Fix Plan

## Root Cause Hypothesis

- Sisyphus had no repository-level value report that combined task state with lifecycle events, so there was no stable way to answer whether MCP stabilization and promotion workflow were paying for their ceremony.
- The pieces needed for the target metrics were split across task state and mixed event logs, and two of the required signals were not emitted explicitly:
  - `session resume time` existed only implicitly in queued/processed inbox log entries
  - `promotion lead time` existed only implicitly in task verify/promotion timestamps
  - `manual intervention count` and `reopen rate after verify` did not have first-class lifecycle events to aggregate

## Fix Strategy

1. Add a repo-level metrics projection that reads both task records and event log entries and produces the four minimum metrics in one place.
2. Add explicit lifecycle instrumentation for:
   - `task.manual_intervention_required`
   - `task.reopened_after_verify`
3. Expose the report through `repo://status/metrics` and include it in `repo://status/board` so the operator surface can read the same numbers.
4. Add regression coverage for both the projection and the new lifecycle events.

## Test Strategy

### Normal Cases

- [x] Repo metrics resource reports session resume time, promotion lead time, and manual intervention count from persisted state and event logs

### Edge Cases

- [x] Parent merge retarget still blocks stacked children and now also emits reopen/manual-intervention signals without regressing the existing promotion flow

### Exception Cases

- [x] Missing or partial event history leaves metrics empty rather than fabricating values

## Verification Mapping

- `Repo metrics resource reports session resume time, promotion lead time, and manual intervention count from persisted state and event logs` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus tests.test_mcp_core tests.test_event_bus`
- `Parent merge retarget still blocks stacked children and now also emits reopen/manual-intervention signals without regressing the existing promotion flow` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus tests.test_mcp_server tests.test_mcp_core tests.test_mcp_adapter tests.test_evolution tests.test_golden tests.test_event_bus`
- `Missing or partial event history leaves metrics empty rather than fabricating values` -> `manual review`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
