# Fix Plan

## Root Cause Hypothesis

- MCP core exposes search/context in source, but one or more runtime entrypoints load an older module path or omit search/context resource templates.
- The launcher/bootstrap may not make repo `src` first in `PYTHONPATH`, or connected clients may keep a stale server process after package updates.

## Fix Strategy

1. Reproduce connected-client discovery for tools and resources using the same bootstrap path users run.
2. Compare MCP core, adapter, server, and launcher exposed tool/resource lists.
3. Add diagnostics for runtime source path, package path, schema version, and search/context surface availability.
4. Repair missing registrations or bootstrap path ordering.
5. Add regression tests covering tool discovery, resource template discovery, `repo://search/status`, and `context://<pack-id>`.
6. Document restart/re-registration requirements if client process caching is unavoidable.

## Design Evaluation

- Design Mode: `light`
- Decision Reason: `repairs runtime exposure of an existing MCP surface`
- Confidence: `medium`
- Layer Impact: `layer-touching`
- Layer Decision Reason: `touches MCP adapter/server/launcher boundaries but not search semantics`
- Required Design Artifacts: `runtime surface matrix`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `runtime surface matrix pending during implementation`

## Test Strategy

### Normal Cases

- [ ] Tool discovery includes `sisyphus.search_index_rebuild`, `sisyphus.search`, and `sisyphus.context_build`.
- [ ] Resource/template discovery includes `repo://search/status` and `context://<context-pack-id>`.
- [ ] Connected bootstrap can build and read a persisted ContextPack.

### Edge Cases

- [ ] Missing search index reports `missing` or rebuilds where expected.
- [ ] Stale or wrong runtime path surfaces a clear diagnostic.
- [ ] Existing task/artifact/evolution MCP resources remain stable.

### Exception Cases

- [ ] Malformed search index surfaces an actionable MCP error.
- [ ] Missing ContextPack id surfaces not-found rather than unsupported-resource.
- [ ] Client discovery failure points to launcher/bootstrap remediation.

## Verification Mapping

- `MCP search/context discovery` -> `python -m unittest tests.test_mcp_core tests.test_mcp_adapter tests.test_mcp_server -v`
- `Launcher/bootstrap runtime path` -> `python -m unittest tests.test_mcp_launcher tests.test_mcp_bootstrap -v`
- `ContextPack resource read` -> `python -m unittest tests.test_search_context.SearchContextTests.test_mcp_search_and_context_surfaces -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
