# Log

## Timeline

- Created task
- Revised the task docs to constrain the slice to generic helper extraction, utils package conversion, and behavior-preserving regression coverage.
- Converted `src/sisyphus/utils.py` into a `src/sisyphus/utils/` package with separate coercion and mapping helper modules.
- Switched `sisyphus.mcp_core` and `sisyphus.evolution.dataset` to import shared helper functions instead of keeping duplicated local coercion helpers.
- Added targeted regression coverage in `tests/test_utils.py` and expanded MCP regression coverage for list coercion validation.

## Notes

- The live repository is currently mid-migration from `taskflow` to `sisyphus`, so this refactor was applied against the active `src/sisyphus` layout in the root workspace rather than the stale pre-adoption task worktree snapshot.
- Domain-specific artifact and evolution policy helpers were intentionally left local; only clearly generic coercion and mapping helpers moved into the shared utils package.

## Follow-ups

- Once the task worktree is rebased or current root changes are adopted into it, the same helper package layout should be mirrored there so closeout no longer depends on a stale source snapshot.
