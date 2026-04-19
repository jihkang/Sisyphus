# Log

## Timeline

- Created task
- Fast-forwarded the task worktree onto the current local baseline so the stage contract work would apply to the current branch state.
- Added `src/taskflow/evolution/stages.py` to define the read-only stage sequence, future-only extension stages, and stage contract metadata.
- Updated `src/taskflow/evolution/runner.py` and the public `sisyphus.evolution` exports so planned runs now carry an explicit `stage`.
- Added tests and documentation for the current read-only stage sequence and the stage-aware failure shape.

## Notes

- The current runtime sequence is now fixed as `planned -> dataset_built -> harness_planned -> constraints_evaluated -> fitness_evaluated -> report_built -> failed`.
- Future review and handoff stages remain documented as future-only and are not presented as active runtime behavior.
- Stage failures now preserve `stage`, `code`, `message`, `partial_results`, and `recoverable` so partial results survive pipeline failure.

## Follow-ups

- Define the evolution-to-Sisyphus handoff payload on top of these stage contracts.
- Implement the read-only orchestrator so it persists stage outputs under `.planning/evolution/runs/<run_id>/`.
