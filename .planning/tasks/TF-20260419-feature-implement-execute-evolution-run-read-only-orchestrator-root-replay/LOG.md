# Log

## Timeline

- Created replay follow-up task from the current root-adopted baseline.
- Linked the replay scope back to `TF-20260418-feature-implement-execute-evolution-run-read-only-orchestrator`, which was already verified but blocked by a stale dirty worktree.
- Replayed the read-only evolution orchestrator on the adopted `sisyphus` baseline by adding `execute_evolution_run(...)` plus append-only run artifact persistence under `.planning/evolution/runs/<run_id>/`.
- Added targeted evolution tests for success, pending-metrics, and stage-failure persistence without live task-state mutation.

## Notes

- Adopted 2016 current changes from branch `feat/sisyphus-naming-unification` into the task worktree, including 49 deletions.
- This replay task preserves the original read-only orchestrator boundary on top of the current `sisyphus` source-of-truth.
- Provider execution, follow-up task creation, and promotion recording remain later tasks.
- Verified with `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /tmp/sisyphus-venv-fresh/bin/python -m unittest tests.test_evolution` in the replay worktree.
- `compileall` was not used as a gate because the sandbox blocks `__pycache__` creation in the worktree.

## Follow-ups

- Build the isolated evaluation executor on top of this persisted run envelope instead of calling the helpers ad hoc.
- Bridge future follow-up requests through Sisyphus lifecycle gates without widening the orchestrator write scope.
