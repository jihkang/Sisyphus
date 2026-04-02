# taskflow-kit

Shared git worktree task lifecycle utility.

Current scope:

- repo-local task state in `.planning/tasks/...`
- per-task git worktree and branch bootstrap
- feature and issue templates
- audit-oriented verify flow
- gate-based escalation

Planned first commands:

- `taskflow new feature <slug>`
- `taskflow new issue <slug>`
- `taskflow verify <task-id>`
- `taskflow close <task-id>`
- `taskflow status`
