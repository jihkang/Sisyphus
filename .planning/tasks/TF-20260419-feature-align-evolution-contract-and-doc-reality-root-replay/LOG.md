# Log

## Timeline

- Created replay follow-up task from the current root-adopted baseline.
- Linked the replay scope back to `TF-20260418-feature-align-evolution-contract-and-doc-reality`, which was already verified but blocked by a stale dirty worktree.
- Added `src/sisyphus/evolution/contracts.py` in the replay worktree to freeze the planning-time evolution vocabulary without implying executor or promotion behavior.
- Updated the replay worktree docs to distinguish current read-only evolution behavior from future executor, MCP surface, and promotion work.
- Added targeted contract coverage in `tests/test_evolution.py` and verified it with the project Python 3.11 environment.

## Notes

- Adopted 2016 current changes from branch `feat/sisyphus-naming-unification` into the task worktree, including 49 deletions.
- This replay task preserves the original contract/doc-alignment boundary on top of the current `sisyphus` source-of-truth.
- Executor, MCP surface, and promotion work remain explicitly future slices.
- The new contract surface names the next slices up front, but the docs explicitly mark review, follow-up, and promotion stages as reserved vocabulary rather than current runtime behavior.

## Follow-ups

- Implement the artifact cycle and read-only orchestrator on top of the newly fixed contract vocabulary.
- Keep future executor, MCP, and promotion tasks aligned to these contract names instead of introducing parallel naming.
