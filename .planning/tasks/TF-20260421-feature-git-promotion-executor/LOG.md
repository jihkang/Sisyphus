# Log

## Timeline

- Created task
- Added git stage/commit/push primitives and a promotion execution orchestrator
- Added API and MCP tool surfaces for the promotion executor
- Verified real git push behavior in a temp bare remote and mocked `gh pr create` output

## Notes

- `promotion.execute_promotion(...)` now writes an `open_pr_receipt.json` artifact under the task directory and updates first-class promotion status through `committed`, `pushed`, and `pr_open`.
- The executor uses the task worktree for git operations and the repo root task directory for promotion receipt artifacts.
- Existing pushed branches can resume at PR-open time without needing a fresh worktree diff.

## Follow-ups

- Wire this executor into the automatic `promotion_pending` workflow and close handoff once merge receipt recording is complete.
