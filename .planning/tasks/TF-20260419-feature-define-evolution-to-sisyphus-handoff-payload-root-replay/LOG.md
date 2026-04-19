# Log

## Timeline

- Created replay follow-up task from the current root-adopted baseline.
- Linked the replay scope back to `TF-20260418-feature-define-evolution-to-sisyphus-handoff-payload`, which was already verified but blocked by a stale dirty worktree.

## Notes

- Adopted 2016 current changes from branch `feat/sisyphus-naming-unification` into the task worktree, including 49 deletions.
- This replay task preserves the original handoff-payload boundary on top of the current `sisyphus` source-of-truth.
- Execution, approval, and receipt authority remain downstream Sisyphus responsibilities.
- Added `src/sisyphus/evolution/handoff.py` in the replay worktree to define the request-only follow-up payload, verification obligations, evidence summaries, promotion intent, and explicit no-self-approval guardrails.
- Updated `docs/self-evolution-mcp-plan.md` and `docs/architecture.md` in the replay worktree so evolution-to-Sisyphus handoff is documented as a reviewable request contract rather than an execution or receipt contract.
- Added `tests/test_evolution.py` in the replay worktree and verified the handoff contract with `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /tmp/sisyphus-venv-fresh/bin/python -m unittest tests.test_evolution`.

## Follow-ups

- Connect this request contract to the later bridge task without adding implicit execution authority.
- Use the same payload shape when the read-only orchestrator begins emitting follow-up candidates.
