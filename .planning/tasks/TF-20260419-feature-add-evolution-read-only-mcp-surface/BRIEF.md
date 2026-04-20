# Brief

## Task

- Task ID: `TF-20260419-feature-add-evolution-read-only-mcp-surface`
- Type: `feature`
- Slug: `add-evolution-read-only-mcp-surface`
- Branch: `feat/add-evolution-read-only-mcp-surface`

## Problem

- The repository already has read-only evolution rendering helpers in `src/sisyphus/evolution/surface.py`, but the MCP layer cannot expose them yet.
- Operators can use the CLI for read-only evolution views, but MCP clients still cannot request run overview, status, report, or compare directly.
- This slice must stay read-only. It must not introduce promotion, follow-up execution, event-bus writes, or mutation of live task state.

## Desired Outcome

- MCP clients can read the same evolution run summaries that the CLI already exposes.
- The MCP surface reuses the existing read-only evolution render/load helpers instead of duplicating evolution logic in the transport layer.
- Missing run IDs fail clearly and predictably through the MCP layer.

## Acceptance Criteria

- [x] `mcp_core` exposes read-only evolution tools for run, status, report, and compare.
- [x] `mcp_core` exposes matching read-only evolution resources so MCP clients can fetch persisted run artifacts without going through task resources.
- [x] The implementation reuses `src/sisyphus/evolution/surface.py` helpers and does not add write-side evolution behavior.
- [x] MCP core/adapter tests cover the new tool and resource paths, including missing-run failure behavior.

## Constraints

- Preserve the current evolution authority boundary: this task is read-only only.
- Do not add promotion, follow-up task creation, provider execution, or event-bus mutation behavior.
- Re-read the task docs before verify and close.
