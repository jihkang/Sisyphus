# Plan

## Implementation Plan

1. Extend the read-only MCP surface with task-scoped artifact resources backed by the existing `project_feature_task(...)` projection instead of introducing new mutation tools.
2. Expose the feature change envelope, projected artifact graph, slot bindings, verification claims, and promotion or invalidation summary as separate MCP resources so operators can inspect each layer independently.
3. Keep the surface feature-task-only for this slice and return clear errors for unsupported task types or incomplete task docs instead of silently fabricating projections.
4. Add focused MCP core tests that prove the new resources are listed in schema output and return reconstructable JSON payloads for a verified feature task.

## Risks

- MCP resources can drift from the underlying projection model if the resource payload shape duplicates artifact logic instead of reusing the typed projection path.
- Read-only artifact inspection must not mutate task state or invoke provider execution while building summaries.

## Test Strategy

### Normal Cases

- [ ] A verified feature task exposes artifact graph, slot bindings, verification claims, and promotion summary resources through MCP.

### Edge Cases

- [ ] A feature task that has not passed verify still returns a candidate projection and a non-promotable summary without failing the resource read.

### Exception Cases

- [ ] Unsupported task types or missing required task docs return actionable errors when reading artifact resources.

## Verification Mapping

- `A verified feature task exposes artifact graph, slot bindings, verification claims, and promotion summary resources through MCP.` -> `python -m unittest -q tests.test_mcp_core`
- `A feature task that has not passed verify still returns a candidate projection and a non-promotable summary without failing the resource read.` -> `python -m unittest -q tests.test_mcp_core tests.test_artifact_projection`
- `Unsupported task types or missing required task docs return actionable errors when reading artifact resources.` -> `python -m unittest -q tests.test_mcp_core tests.test_artifact_projection`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
