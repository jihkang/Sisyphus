# Changeset

## Code

- Extended `src/sisyphus/evolution/harness.py` with a full worktree-backed evaluation executor that derives normalized command plans, runs commands inside isolated evaluation worktrees, captures receipts, and returns runtime-aware evidence.
- Extended `src/sisyphus/evolution/dataset.py` so evolution task traces carry declared `verify_commands` in addition to prior verify results.
- Exported the new worktree-backed executor surface from `src/sisyphus/evolution/__init__.py`.

## Tests

- Expanded `tests/test_evolution.py` to cover command normalization, command-plan de-duplication, successful receipt capture, and failure-path receipt persistence for worktree-backed execution.
- Verified with:
  - `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
  - `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution tests.test_artifact_evaluator tests.test_artifact_projection tests.test_artifacts tests.test_utils`

## Docs

- Updated `docs/self-evolution-mcp-plan.md` and `docs/architecture.md` so they no longer describe full worktree-backed harness execution as future work.
- Updated task-local BRIEF, PLAN, VERIFY, and LOG docs to match the implemented executor slice.
