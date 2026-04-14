# Log

## Timeline

- Created task
- Approved the plan and froze the constraints/fitness scope for a read-only model layer.
- Added `constraints.py` and `fitness.py` plus package exports for the new evaluation models.
- Extended `tests/test_evolution.py` to cover pending, accepted, and rejected guard/fitness flows.
- Ran `./.venv/bin/python -m unittest tests.test_evolution -v`.

## Notes

- Hard guards are intentionally blocking only on verify pass rate, drift count, unresolved warnings, MCP compatibility, and output contract stability.
- Fitness scoring stays usable for future executed harness outputs while remaining pending on plan-only inputs.

## Follow-ups

- Wire executed harness metrics into these models once evolution execution exists.
