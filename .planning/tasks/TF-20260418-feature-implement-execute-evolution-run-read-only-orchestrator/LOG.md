# Log

## Timeline

- Created task
- Fast-forwarded the task worktree onto the current local baseline so the read-only orchestrator could target the current evolution modules.
- Added `src/taskflow/evolution/orchestrator.py` with `execute_evolution_run(...)`, append-only run artifact persistence, and stage-aware failure capture.
- Exported the orchestrator surface through `taskflow.evolution` and `sisyphus.evolution`, and added regression tests for success, pending metrics, and failure persistence.
- Updated the evolution docs to describe the new read-only entrypoint and its write boundary.

## Notes

- `execute_evolution_run(...)` now composes run planning, dataset extraction, harness planning, constraints evaluation, fitness evaluation, report generation, and run artifact persistence.
- The allowed write scope is restricted to `.planning/evolution/runs/<run_id>/`, where the orchestrator stores `run.json`, `dataset.json`, `harness_plan.json`, `constraints.json`, `fitness.json`, `report.md`, and `failure.json` on error.
- Pending constraints and fitness remain explicit pending states when metrics are unavailable; the orchestrator does not fabricate pass/fail results.

## Follow-ups

- Build the isolated evaluation executor on top of this persisted run envelope instead of calling the helpers ad hoc.
- Bridge future follow-up requests through Sisyphus lifecycle gates without widening the orchestrator write scope.
