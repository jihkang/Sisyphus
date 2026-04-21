# Log

## Timeline

- Created issue task from the promotion/MCP roadmap umbrella
- Added `src/sisyphus/metrics.py` to project repository value metrics from task state and mixed event logs
- Exposed `repo://status/metrics` and attached the same report to `repo://status/board`
- Added lifecycle instrumentation for `task.manual_intervention_required` and `task.reopened_after_verify`
- Added regression coverage for metrics projection, MCP resource reads, and stacked-child reopen signaling
- Approved the fix plan, froze the scope, verified the task through Sisyphus MCP, and closed the task

## Notes

- Metrics now derive:
  - session resume time from queued/processed inbox events
  - reopen rate after verify from explicit reopen signals plus current reverify flags
  - promotion lead time from `last_verified_at -> promotion.recorded_at`
  - manual intervention count from explicit lifecycle events
- Metric events are written to `.planning/events.jsonl` even when the configured event bus provider is `noop`, so the default local repository still accumulates value data.
- The live Sisyphus MCP server in this session may need a restart before `repo://status/metrics` appears in the active resource list.
- The MCP close call completed, but the stale server process still wrote `workflow_phase=verified` alongside `status=closed` in `task.json`; the task is closed, but the server should be restarted before trusting that projection detail.

## Follow-ups

- Decide whether `repo://status/board` should surface only the top-line metric summary instead of the full nested metrics payload
- Add a CLI/status rendering path for the same value report if operators need the numbers outside MCP
