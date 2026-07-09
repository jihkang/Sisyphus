# Changeset

## Summary

- Extended episode trace artifacts with state snapshots, deterministic episode ids, step calculation, JSONL reading, and trace validation.
- Wired task-scoped MCP mutation tools to record action/result/state transition steps under `artifacts/episodes/`.
- Added `sisyphus episode check <task-id>` for read-only trace validation and action sequence summaries.

## Files

- `src/sisyphus/episode_trace.py`
- `src/sisyphus/mcp_core.py`
- `src/sisyphus/cli.py`
- `tests/test_episode_trace.py`
- `tests/test_mcp_core.py`
- `tests/test_sisyphus.py`

## Follow-up

- The explicit test-first implementation loop is deferred to the eval/loop task so it can be modeled as a first-class harness phase.
