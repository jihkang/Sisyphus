# Log

## Timeline

- Created task

## Notes

- This slice adds evolution-scoped envelope-bus events to existing hard-state slices only.
- CLI/MCP surface expansion and orchestration-loop behavior stay out of scope.
- Implemented `src/sisyphus/evolution/event_bus.py` plus emission hooks from orchestrator, follow-up bridge, receipt projection, verification projection, and decision-envelope recording, with focused event assertions in `tests/test_evolution.py`.

## Follow-ups

- After this slice, the remaining dedicated backlog is the artifact-cycle end-to-end vertical test task.
