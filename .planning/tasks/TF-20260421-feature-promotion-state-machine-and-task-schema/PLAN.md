# Plan

## Implementation Plan

1. Introduce a shared promotion-state helper that defines the first-class task schema, normalizes valid promotion statuses and strategies, and migrates legacy `meta["promotion"]` data into task state.
2. Extend task record defaults so load/list/save always carry a normalized promotion bundle with branch, PR, receipt, and lineage fields.
3. Rewire current readers and writers so merge-receipt recording, MCP task projections, service summaries, and evolution follow-up receipt projection all consume the same first-class promotion state.
4. Add regressions covering default task schema, legacy migration, merge receipt recording, MCP promotion projections, service summaries, and evolution receipt projection.

## Risks

- Promotion state now lives on the shared task record path, so bad normalization could leak into unrelated MCP, API, CLI, or evolution flows.
- Backward compatibility matters because older code paths and historical tasks still carry `meta["promotion"]` rather than a first-class promotion bundle.

## Design Evaluation

- Design Mode: `light`
- Decision Reason: `touches shared task state, MCP projections, service summaries, and evolution receipt readers without introducing a new runtime layer`
- Confidence: `high`
- Layer Impact: `layer-touching`
- Layer Decision Reason: `this establishes a common state contract between existing promotion-adjacent layers`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `promotion state now normalizes through task state before downstream projections read it`

## Test Strategy

### Normal Cases

- [x] New tasks initialize a first-class promotion bundle with stable defaults.
- [x] Merge receipt recording writes the promotion terminal state into task state and keeps legacy meta compatibility.
- [x] MCP task record/status projections expose promotion state to clients.

### Edge Cases

- [x] Older tasks that only have `meta["promotion"]` migrate into the first-class promotion bundle when loaded.
- [x] Evolution follow-up receipt projection accepts promotion receipts from the first-class bundle and ignores default receipt paths when no promotion has actually occurred.

### Exception Cases

- [x] Evolution follow-up receipt projection still fails clearly when a task claims a recorded promotion receipt but the file is missing.

## Verification Mapping

- `New tasks initialize a first-class promotion bundle with stable defaults` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus`
- `Merge receipt recording writes the promotion terminal state into task state and keeps legacy meta compatibility` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus tests.test_mcp_core`
- `MCP task record/status projections expose promotion state to clients` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_mcp_core`
- `Older tasks that only have meta[\"promotion\"] migrate into the first-class promotion bundle when loaded` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus`
- `Evolution follow-up receipt projection accepts promotion receipts from the first-class bundle and ignores default receipt paths when no promotion has actually occurred` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_evolution`
- `Evolution follow-up receipt projection still fails clearly when a task claims a recorded promotion receipt but the file is missing` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_evolution`
- `Shared task-state and MCP/evolution flows stay stable after the schema change` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus tests.test_mcp_server tests.test_mcp_core tests.test_mcp_adapter tests.test_evolution tests.test_golden`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
