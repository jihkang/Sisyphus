# Sisyphus Agent Guidance

Use the Sisyphus MCP server for task lifecycle operations before editing repository-local task state directly.

## Required MCP Usage

- Use Sisyphus MCP tools for `request_task`, plan review transitions, spec freeze, subtask generation, verify, close, and daemon processing.
- Read `task://<task-id>/record` and `task://<task-id>/conformance` before continuing work on an existing task.
- Read the task docs from MCP resources such as `task://<task-id>/brief`, `task://<task-id>/plan`, `task://<task-id>/verify`, and `task://<task-id>/log` before making execution decisions.
- Prefer MCP resources over manually editing `.planning/tasks/...` files unless you are explicitly working on Sisyphus internals.

## Conformance Discipline

- Treat `green` as spec-aligned.
- Treat `yellow` as unresolved drift or clarification that must be surfaced and resolved before final verify.
- Treat `red` as blocking drift and stop execution until it is resolved.
- Check the latest spec anchor time, checkpoint type, drift count, and last warning or failure summary before resuming work.

## Operational Rules

- Do not invent task state transitions outside the Sisyphus workflow.
- Do not mark tasks verified or closed without using Sisyphus verify and close operations.
- If task docs and implementation disagree, prefer the frozen task docs and reconcile code to the documented scope unless the operator explicitly revises the plan or spec.
- If conformance is `yellow` or `red`, call it out explicitly in your response instead of silently continuing.

## Suggested Startup Behavior

- On a new request, create or inspect the task through the Sisyphus MCP server first.
- On an existing task, load both the task record and conformance resource before planning the next action.
- Use Sisyphus status views or task resources to understand blockers, gates, subtasks, and agent state before editing code.
