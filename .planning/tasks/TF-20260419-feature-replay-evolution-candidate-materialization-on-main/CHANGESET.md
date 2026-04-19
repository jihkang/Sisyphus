# Changeset

## Code

- Added `src/sisyphus/evolution/materialization.py` with bounded baseline/candidate snapshot materialization for isolated evaluation worktrees.
- Updated `src/sisyphus/evolution/harness.py` to materialize evaluation inputs before provider execution and to persist materialization evidence in evaluation outcomes.
- Exported the new materialization surface from `src/sisyphus/evolution/__init__.py`.

## Tests

- Expanded `tests/test_evolution.py` to cover baseline capture, candidate rewrites, missing-anchor failure, and harness evidence/owned-path propagation.
- Removed duplicated helper definitions introduced while replaying the slice so the test diff stays minimal and maintainable.

## Docs

- Updated `docs/self-evolution-mcp-plan.md` and `docs/architecture.md` to reflect that bounded candidate materialization is now implemented.
- Recorded task verification and execution notes in the task-local docs for this replay branch.
