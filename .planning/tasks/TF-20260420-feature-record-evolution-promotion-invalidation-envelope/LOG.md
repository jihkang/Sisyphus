# Log

## Timeline

- Created task
- Replaced the generic scaffold with a recording-only slice focused on turning promotion-gate outputs into reconstructable promotion or invalidation envelopes.
- Extended the evolution record contracts so promotion decisions and invalidation records retain candidate identity, blocker detail, evidence refs, and follow-up task linkage.
- Added envelope recording helpers and regression tests, then confirmed `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution` passed.

## Notes

- This slice should record promotion or invalidation state from existing hard-state inputs instead of recomputing later from scattered artifacts.
- Event-bus publication and invalidation-policy derivation remain explicitly out of scope for this task.

## Follow-ups

- After this slice, the remaining dedicated work is invalidation-rule definition, event envelope integration, and artifact-cycle end-to-end tests.
