# Log

## Timeline

- Created task
- Identified that only planning/audit flows hydrated docs-derived `test_strategy` and `design`, leaving MCP/API/CLI loads on stale defaults.
- Added a shared task-projection normalization helper in `state.py` and routed load/list/save through it.
- Added regressions covering load/list projections and MCP task-record reads after editing task docs.
- Ran focused and broader unittest suites to confirm central normalization did not regress adjacent flows.
- Extended normalization so stale closed task records are projected back as `workflow_phase=closed`.

## Notes

- `load_task_record` and `list_task_records` previously returned only `ensure_task_record_defaults(...)`, so `PLAN.md` edits were invisible until another lifecycle function happened to sync them.
- Centralizing normalization in `state.py` means MCP record resources, API `get_task/list_tasks`, CLI status, and other callers now see the same projection contract by default.
- Terminal lifecycle state is now canonicalized as part of projection normalization, so a stale `status=closed` record can no longer leak `workflow_phase=verified` through newer reads.

## Follow-ups

- Use this normalized task state as the base for `TF-20260421-feature-promotion-state-machine-and-task-schema`, where promotion metadata should project consistently across task records and MCP surfaces.
