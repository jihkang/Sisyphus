# Plan

## Implementation Plan

1. Extend `src/sisyphus/mcp_core.py` so the MCP tool/resource registry includes read-only evolution run entries for overview, status, report, and compare.
2. Route those MCP entries through `src/sisyphus/evolution/surface.py` so loading, formatting, and compare behavior stays centralized.
3. Add MCP core and adapter tests that cover successful reads plus missing-run failures.
4. Update task docs and verification commands so this slice can be verified and closed without scope drift.

## Risks

- Tool/resource naming can drift from the existing Sisyphus MCP conventions if the surface is added inconsistently.
- Missing run IDs need a deterministic MCP error path or clients will get ambiguous failures.
- If the MCP layer reimplements evolution formatting instead of reusing `surface.py`, the CLI and MCP surfaces will drift.

## Test Strategy

### Normal Cases

- [x] MCP tool returns evolution run overview, status, report, and compare output for persisted run artifacts
- [x] MCP resource reads return the same persisted evolution views for overview, status, report, and compare

### Edge Cases

- [x] Compare works across two persisted runs with different stage/result combinations

### Exception Cases

- [x] Missing evolution run IDs raise a clear not-found error through MCP tool/resource calls

## Verification Mapping

- `MCP tool returns evolution run overview, status, report, and compare output for persisted run artifacts` -> `python -m unittest -q tests.test_mcp_core tests.test_mcp_adapter tests.test_mcp_server`
- `MCP resource reads return the same persisted evolution views for overview, status, report, and compare` -> `python -m unittest -q tests.test_mcp_core tests.test_mcp_adapter tests.test_mcp_server`
- `Compare works across two persisted runs with different stage/result combinations` -> `python -m unittest -q tests.test_mcp_core tests.test_mcp_adapter tests.test_mcp_server`
- `Missing evolution run IDs raise a clear not-found error through MCP tool/resource calls` -> `python -m unittest -q tests.test_mcp_core tests.test_mcp_adapter tests.test_mcp_server`
- `Transport-facing MCP surface still imports cleanly after the new read-only routes are added` -> `python -m compileall -q src`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
