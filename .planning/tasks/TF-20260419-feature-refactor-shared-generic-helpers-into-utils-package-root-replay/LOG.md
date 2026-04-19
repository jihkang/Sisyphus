# Log

## Timeline

- Created replay follow-up task from the current root-adopted baseline.
- Linked the replay scope back to `TF-20260419-feature-refactor-shared-generic-helpers-into-utils-package`, which was already verified but blocked by a stale dirty worktree.
- Confirmed the adopted replay worktree already contains the `src/sisyphus/utils/` package split plus shared helper imports in `sisyphus.mcp_core` and `sisyphus.evolution.dataset`.
- Revalidated the replay scope with focused regression tests instead of widening the refactor beyond the existing generic helper boundary.

## Notes

- Adopted 2016 current changes from branch `feat/sisyphus-naming-unification` into the task worktree, including 49 deletions.
- This replay task preserves the original helper-refactor boundary on top of the current `sisyphus` source-of-truth.
- Domain-specific artifact and evolution policy helpers remain local; only clearly generic coercion and mapping helpers belong in the shared utils package.
- Verified with `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_utils`.
- Verified with `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_mcp_core`.

## Follow-ups

- Once the task worktree matches the current root source snapshot, the utils package layout and caller imports can be closed without stale-baseline drift.
