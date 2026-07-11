# Contributing to Sisyphus

Sisyphus is a repository-local control plane for AI-assisted software work. Changes must preserve durable task state, lifecycle gates, compatibility surfaces, and reconstructable verification evidence.

## Development Setup

Requirements:

- Python 3.11 or newer
- `uv`
- `git`

Create the locked development environment from the repository root:

```bash
uv lock --check
uv sync --frozen --all-extras --group dev
```

Run the CLI from the environment with `uv run --frozen sisyphus ...`.

## Task Workflow

Use Sisyphus itself for repository work:

1. Create or inspect a task through the Sisyphus CLI or MCP server.
2. Read `task://<task-id>/observation` before choosing the next action.
3. Keep implementation inside the task branch and worktree.
4. Treat plan approval, spec freeze, close, promotion, and merge recording as operator decisions.
5. Run verification before promotion and record the merged pull request before closing the task.

Do not edit `task.json` to bypass lifecycle or action-registry rules. Prefer Sisyphus MCP resources and tools over direct task-state edits.

## Change Scope

- Keep pull requests focused on one responsibility or migration slice.
- Preserve public imports and persisted identifiers unless the change explicitly includes a compatibility plan.
- Add abstractions only when they remove measured duplication or establish a documented ownership boundary.
- Do not reformat or refactor unrelated files.
- Add tests at the boundary where behavior changes.

The canonical implementation package is `src/sisyphus`. Top-level modules such as `sisyphus.cli`, `sisyphus.state`, and `sisyphus.workflow` may intentionally remain compatibility facades over `interfaces`, `domain`, `infra`, and `shared` packages.

## Verification

Run the same core checks used by CI:

```bash
uv lock --check
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen --all-extras --group dev coverage run -m unittest discover -s tests
uv run --frozen --all-extras --group dev coverage report
uv build --no-sources
```

Coverage uses branch measurement and currently enforces an 80% repository-wide floor. New behavior should normally include focused assertions even when the total percentage remains above the floor.

## Pull Requests

A pull request should state:

- the problem and bounded scope
- compatibility or migration impact
- tests and verification commands run
- remaining limitations or follow-up work
- the associated Sisyphus task ID when one exists

All required CI jobs must pass before merge. Prefer squash merge for a focused task branch unless preserving individual commits is important to the change history.

## Releases

Versioning and release gates are defined in [RELEASES.md](RELEASES.md). A merged change is not a release by itself.
