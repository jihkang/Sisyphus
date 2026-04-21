# Log

## Timeline

- Created task
- Added close handoff inside merge receipt recording and surfaced the outcome through daemon/API/MCP results
- Added regression coverage for both unverified and verified promotion-pending merge receipt paths
- Ran targeted and full unittest regression suites

## Notes

- `record_merged_pull_request(...)` now attempts `run_close(..., allow_dirty=True)` when the task has already passed verify and is still open.
- Merge receipt processing now reports `close_attempted`, `closed`, `close_status`, and `close_gate_codes` instead of leaving close eligibility implicit.
- Unverified tasks still record the merge receipt but stay open until verify passes.

## Follow-ups

- Fold this handoff into stacked promotion once parent and child PR lineage is available.
