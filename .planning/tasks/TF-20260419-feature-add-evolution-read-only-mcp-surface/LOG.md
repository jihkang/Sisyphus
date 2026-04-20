# Log

## Timeline

- 2026-04-19: Created the task through the Sisyphus CLI fallback because the live MCP `request_task` session still pointed at the removed `src/taskflow/templates_data` path.
- 2026-04-19: Rewrote the task brief/plan, approved the plan, froze the spec, and generated subtasks through Sisyphus MCP.
- 2026-04-20: Added the read-only evolution MCP tools/resources in `src/sisyphus/mcp_core.py`, updated MCP tests, and aligned `docs/self-evolution-mcp-plan.md` with the implemented surface.
- 2026-04-20: Verified against the task worktree branch and closed the task with `allow_dirty=true` because the root worktree still contains unrelated untracked files outside this slice.

## Notes

- The implemented MCP surface is intentionally read-only. It reuses `src/sisyphus/evolution/surface.py` and does not start runs, materialize candidates, approve follow-up work, or write promotion state.
- Evolution compare is exposed as `evolution://compare/<left-run-id>/<right-run-id>` to keep the resource URI read-only and explicit.
- Verification was executed against the task worktree so the receipt reflects the task branch content rather than only the root shuttle branch.

## Follow-ups

- Write-side evolution MCP ingress remains deferred until the handoff contract, receipts, and promotion/invalidation envelopes are in place.
