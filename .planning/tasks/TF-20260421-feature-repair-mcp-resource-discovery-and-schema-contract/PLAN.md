# Plan

## Implementation Plan

1. Generalize MCP resource/template discovery so URI placeholders are detected from any `<token>` pattern, converted into MCP template variables, and invalid definitions are skipped without failing the whole listing.
2. Repair the published schema/reference surface by listing missing task docs such as `task://<task-id>/repro` and normalizing markdown MIME handling for task and evolution resources.
3. Make resource reads stable before later lifecycle stages exist by returning placeholders for missing `promotion` and `changeset` artifacts and explicit unavailable payloads for feature-only artifact resources on non-feature tasks.
4. Lock the behavior down with focused MCP server/core/adapter regression tests and update the task docs to match the implemented contract.

## Risks

- Discovery changes can silently regress resource listings if template detection or MIME mapping drifts from the underlying MCP server implementation.
- Returning placeholders for not-yet-recorded resources must preserve a stable shape without hiding genuine read failures for supported task docs.

## Design Evaluation

- Design Mode: `light`
- Decision Reason: `crosses the MCP server, MCP core service, and test surfaces but does not add a new runtime layer`
- Confidence: `high`
- Layer Impact: `layer-touching`
- Layer Decision Reason: `the task tightens contracts between existing resource discovery, schema publication, and read surfaces`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `existing MCP server/core boundary preserved`

## Test Strategy

### Normal Cases

- [x] Resource listing cleanly separates concrete resources from template resources across task and evolution URI patterns.
- [x] MCP clients can discover the full intended schema, including `task://<task-id>/repro`, without stale entries breaking the list.

### Edge Cases

- [x] Invalid URI definitions in the published resource list are skipped instead of crashing discovery.
- [x] Pre-merge `promotion` and `changeset` resources return stable placeholders instead of raising file-not-found errors.

### Exception Cases

- [x] Feature-only artifact resources read from issue tasks return explicit unavailable payloads instead of leaking projection exceptions.

## Verification Mapping

- `Resource listing cleanly separates concrete resources from template resources across task and evolution URI patterns` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_mcp_server`
- `MCP clients can discover the full intended schema, including task://<task-id>/repro, without stale entries breaking the list` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_mcp_core tests.test_mcp_adapter`
- `Invalid URI definitions in the published resource list are skipped instead of crashing discovery` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_mcp_server`
- `Pre-merge promotion and changeset resources return stable placeholders instead of raising file-not-found errors` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_mcp_core`
- `Feature-only artifact resources read from issue tasks return explicit unavailable payloads instead of leaking projection exceptions` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_mcp_core`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
