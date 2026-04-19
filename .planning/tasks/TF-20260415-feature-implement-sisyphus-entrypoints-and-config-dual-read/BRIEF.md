# Brief

## Task

- Task ID: `TF-20260415-feature-implement-sisyphus-entrypoints-and-config-dual-read`
- Type: `feature`
- Slug: `implement-sisyphus-entrypoints-and-config-dual-read`
- Branch: `feat/implement-sisyphus-entrypoints-and-config-dual-read`

## Problem

- The repository still routes canonical CLI and MCP entrypoints through `taskflow.*` modules.
- Repo configuration discovery still recognizes only `.taskflow.toml`.
- The next migration slice should introduce canonical `sisyphus` module entrypoints and dual-read config support without breaking existing `taskflow` compatibility.

## Desired Outcome

- `sisyphus.cli` and `sisyphus.mcp_server` exist as canonical module entrypoints for console scripts and direct `python -m ...` usage.
- `taskflow` module paths remain available as compatibility shims.
- Config loading and repo-root detection prefer `.sisyphus.toml` and fall back to `.taskflow.toml`.
- Docs and wrapper examples present the new canonical module path and config filename while documenting legacy compatibility where needed.

## Acceptance Criteria

- [ ] `pyproject.toml` points canonical console scripts at `sisyphus.cli:main` and `sisyphus.mcp_server:main`.
- [ ] `python -m sisyphus.mcp_server` and `python -m sisyphus.cli` work through canonical wrapper modules.
- [ ] `load_config()` and repo-root detection prefer `.sisyphus.toml` and still accept `.taskflow.toml`.
- [ ] Docs and examples use canonical `sisyphus.mcp_server` and `.sisyphus.toml`, with legacy compatibility still described accurately.
- [ ] Regression tests cover canonical module aliases and config precedence.

## Constraints

- Preserve `taskflow` runtime compatibility for imports, scripts, and legacy config files.
- Do not rename `src/taskflow/`, `taskflow.event.v1`, or `TF-...` task ids in this slice.
- Keep user-facing examples truthful to the code that exists after this change.
- Re-read the task docs before verify and close.
