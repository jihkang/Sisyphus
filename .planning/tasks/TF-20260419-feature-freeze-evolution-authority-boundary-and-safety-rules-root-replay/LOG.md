# Log

## Timeline

- Created replay follow-up task from the current root-adopted baseline.
- Linked the replay scope back to `TF-20260418-feature-freeze-evolution-authority-boundary-and-safety-rules`, which was already verified but blocked by a stale dirty worktree.
- Updated the replay worktree copies of `docs/architecture.md` and `docs/self-evolution-mcp-plan.md` to restate the evolution versus Sisyphus authority boundary in explicit normative language.

## Notes

- Adopted 2016 current changes from branch `feat/sisyphus-naming-unification` into the task worktree, including 49 deletions.
- This replay task preserves the original authority-boundary wording on top of the current `sisyphus` source-of-truth.
- The replay worktree now explicitly marks the harness executor as evaluation-only, limits read-only orchestration to append-only `.planning/evolution/runs/<run_id>/` artifacts, and forbids evolution from approving, freezing, or promoting its own follow-up work.
- Runtime execution, bridge logic, and promotion recording remain later tasks.

## Follow-ups

- Align the remaining evolution docs and contracts with this authority boundary.
- Implement the append-only evolution run artifact cycle and read-only orchestrator in follow-up tasks.
