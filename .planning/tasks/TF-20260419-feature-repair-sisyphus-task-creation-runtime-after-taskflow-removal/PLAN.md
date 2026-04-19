# Plan

## Implementation Plan

1. Trace the active `request_task` call path from MCP/API/CLI into task creation and template resolution, and identify where the stale `taskflow/templates_data` lookup is still being introduced.
2. Repair the runtime so task creation resolves templates only from Sisyphus-owned sources, with the same behavior across MCP, API, and CLI entrypoints.
3. Add targeted regression tests that reproduce the stale-path failure and lock the corrected runtime behavior.
4. Update task docs and verification notes to reflect the actual repaired code path and bounded scope.

## Risks

- The stale reference may live in an installed/runtime indirection rather than the obvious repository code path.
- Fixing one entrypoint but not the shared runtime path would leave MCP and CLI behavior divergent.
- Template resolution changes can regress task provisioning if the tests only cover the happy path.

## Test Strategy

### Normal Cases

- [x] API and MCP task creation resolve Sisyphus feature templates successfully after the repair.

### Edge Cases

- [x] Task creation still works when repo root is explicit and the current working directory differs.
- [x] The runtime does not silently fall back to `taskflow` template paths when feature and issue templates are resolved.

### Exception Cases

- [x] If template data is truly missing, task creation surfaces an actionable Sisyphus-scoped error instead of a stale taskflow path.

## Verification Mapping

- `API and MCP task creation resolve Sisyphus feature templates successfully after the repair.` -> `python -m unittest -q tests.test_sisyphus tests.test_mcp_core`
- `Task creation still works when repo root is explicit and the current working directory differs.` -> `python -m unittest -q tests.test_sisyphus`
- `The runtime does not silently fall back to taskflow template paths when feature and issue templates are resolved.` -> `python -m unittest -q tests.test_sisyphus`
- `If template data is truly missing, task creation surfaces an actionable Sisyphus-scoped error instead of a stale taskflow path.` -> `targeted regression test`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
