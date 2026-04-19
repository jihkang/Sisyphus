# Log

## Timeline

- Created replay follow-up task from the current root-adopted baseline.
- Linked the replay scope back to `TF-20260418-feature-define-evolution-stage-transition-and-failure-contract`, which was already verified but blocked by a stale dirty worktree.

## Notes

- Adopted 2016 current changes from branch `feat/sisyphus-naming-unification` into the task worktree, including 49 deletions.
- This replay task preserves the original stage/failure contract boundary on top of the current `sisyphus` source-of-truth.
- Harness execution, bridge execution, and promotion runtime logic remain later tasks.
- Added `src/sisyphus/evolution/stage_contracts.py` in the replay worktree to define the initial read-only stage registry, stage-by-stage contract metadata, and stage-aware failure payload shape.
- Updated `docs/self-evolution-mcp-plan.md` and `docs/architecture.md` in the replay worktree so the initial stage sequence and future-only extension stages are documented separately.
- Added `tests/test_evolution.py` in the replay worktree and verified the stage contract with `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /tmp/sisyphus-venv-fresh/bin/python -m unittest tests.test_evolution`.

## Follow-ups

- Define the evolution-to-Sisyphus handoff payload on top of these stage contracts.
- Implement the read-only orchestrator so it persists stage outputs under `.planning/evolution/runs/<run_id>/`.
