# Log

## Timeline

- Created task

## Notes

- This slice should define explicit change classes and remediation actions for evolution invalidation without adding orchestration.
- Event publication and end-to-end orchestration stay out of scope.
- Implemented `src/sisyphus/evolution/invalidation.py` with explicit change/action vocabularies, deterministic remediation ordering, stale-artifact ref dedupe, and focused unit coverage in `tests/test_evolution.py`.

## Follow-ups

- After this slice, the remaining dedicated work is event-envelope integration and artifact-cycle end-to-end tests.
