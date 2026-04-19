# Brief

## Task

- Task ID: `TF-20260415-feature-plan-naming-unification-to-sisyphus`
- Type: `feature`
- Slug: `plan-naming-unification-to-sisyphus`
- Branch: `feat/plan-naming-unification-to-sisyphus`

## Problem

- The repository currently mixes `taskflow` and `Sisyphus` across user-facing surfaces.
- This execution slice should implement only the safe surface-cleanup phase from the plan.
- High-risk identifiers such as module paths, config filenames, event schema identifiers, and task id prefixes remain out of scope for this slice.

## Desired Outcome

- The CLI help and generated task-doc guidance prefer `sisyphus` as the canonical command surface.
- User docs and wrapper docs make it clear that `taskflow.mcp_server` is still the current compatibility launcher path where applicable.
- Existing `taskflow` runtime compatibility remains intact.
- Assumption: the intended canonical spelling is `Sisyphus`; `Sispyhus` in the request is treated as a typo for this slice.

## Acceptance Criteria

- [ ] `build_parser()` presents `sisyphus` as the CLI program name.
- [ ] Generated feature and issue verification mappings use `sisyphus verify` instead of `taskflow verify`.
- [ ] User-facing MCP setup docs explain that `taskflow.mcp_server` is a compatibility launcher path rather than the canonical brand surface.
- [ ] Regression tests cover the updated CLI/help and generated-plan wording without removing `taskflow` compatibility behavior.

## Constraints

- Preserve existing external compatibility where a rename would break installed commands, Python imports, MCP entry points, config discovery, or event consumers.
- Do not rename `src/taskflow/`, `.taskflow.toml`, `taskflow.event.v1`, or `TF-...` in this slice.
- Keep documentation examples technically correct for the current codebase.
- Re-read the task docs before verify and close.
