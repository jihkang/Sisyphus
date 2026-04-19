# Log

## Timeline

- Created replay follow-up task from the current root-adopted baseline.
- Linked the replay scope back to `TF-20260418-feature-define-evolution-artifact-cycle-interface`, which was already verified but blocked by a stale dirty worktree.
- Added `src/sisyphus/evolution/artifacts.py` in the replay worktree with a shared artifact base, explicit ownership split, and the minimum evolution artifact kinds for the next vertical slice.
- Updated the replay worktree docs so artifact ownership, reconstructability fields, and future-only persistence boundaries are explicit.
- Added targeted artifact-interface coverage in `tests/test_evolution.py` and verified it with the project Python 3.11 environment.

## Notes

- Adopted 2016 current changes from branch `feat/sisyphus-naming-unification` into the task worktree, including 49 deletions.
- This replay task preserves the original artifact-cycle interface boundary on top of the current `sisyphus` source-of-truth.
- A universal artifact engine, runtime persistence expansion, and surface APIs remain out of scope.
- Evolution-owned planning artifacts and Sisyphus-owned authoritative artifacts are now split by type-level defaults instead of duplicated per-class field definitions.

## Follow-ups

- Use these artifact types when defining the read-only orchestrator and stage-transition contract.
- Attach runtime persistence and receipt generation only in the later executor and bridge tasks.
