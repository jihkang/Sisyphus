# Log

## Timeline

- Created task
- Fast-forwarded the task worktree onto the current `main` baseline so the authority-boundary edits would apply to the latest evolution docs.
- Updated `docs/architecture.md`, `docs/self-evolution-mcp-plan.md`, and `docs/philosophy.md` to freeze the evolution versus Sisyphus authority boundary.

## Notes

- Documented that `evolution` is the soft-cognition and evaluation layer, while Sisyphus remains the hard-state and execution authority.
- Defined the harness executor as evaluation-only and prohibited it from mutating live repository or live task state.
- Defined `read-only` as allowing append-only artifacts under `.planning/evolution/runs/<run_id>/` while forbidding mutation of `src/`, `templates/`, and `.planning/tasks/<live_task_id>/`.
- Removed or replaced wording that implied evolution could approve, freeze, or promote its own follow-up work.

## Follow-ups

- Align the remaining evolution docs and contracts with this authority boundary.
- Implement the append-only evolution run artifact cycle and read-only orchestrator in follow-up tasks.
