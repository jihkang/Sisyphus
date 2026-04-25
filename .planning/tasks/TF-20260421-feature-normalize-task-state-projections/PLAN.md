# Plan

## Implementation Plan

1. Move docs-derived task hydration into a shared state normalization helper so `load_task_record`, `list_task_records`, and `save_task_record` all apply the same `PLAN.md` / `FIX_PLAN.md` sync.
2. Remove reliance on a few ad hoc planning/audit call sites by letting MCP record resources, API task reads, and status-oriented projections inherit the normalized task state automatically.
3. Add regression coverage that proves normal task loads and MCP task-record resources expose synced `test_strategy` and `design` fields after only editing the task docs.
4. Canonicalize terminal closed-state projection so stale `status=closed` records cannot keep `workflow_phase=verified` in newer reads.
5. Update task docs to capture the normalized-path contract and the verification coverage that passed.

## Risks

- A state-layer normalization hook can accidentally change task behavior in unrelated flows if it mutates records differently across load/list/save paths.
- Saving normalized state must stay safe even when task docs are incomplete or still on placeholder templates.
- Closed-task canonicalization must not broaden into unrelated status rewrites for non-terminal tasks.

## Design Evaluation

- Design Mode: `light`
- Decision Reason: `touches the shared state-loading path used by MCP, API, CLI, and lifecycle helpers but does not introduce a new runtime layer`
- Confidence: `high`
- Layer Impact: `layer-touching`
- Layer Decision Reason: `this tightens the boundary between persisted task records and docs-derived projection state`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `task projection normalization now lives in state.py`

## Test Strategy

### Normal Cases

- [x] Loading and listing a task after editing `PLAN.md` surfaces the same doc-derived `test_strategy` and `design` state.
- [x] MCP `task://.../record` reads return the normalized projection instead of raw stale defaults.

### Edge Cases

- [x] Save-time normalization stays safe for tasks whose docs are still incomplete or partially templated.
- [x] Existing planning, MCP, evolution, and golden-template tests continue to pass after centralizing normalization.
- [x] Stale closed tasks are read back as `workflow_phase=closed` instead of preserving an outdated in-memory phase.

### Exception Cases

- [x] Missing or partial plan sections do not crash task load/list projections.

## Verification Mapping

- `Loading and listing a task after editing PLAN.md surfaces the same doc-derived test_strategy and design state` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus`
- `MCP task://.../record reads return the normalized projection instead of raw stale defaults` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_mcp_core`
- `Save-time normalization stays safe for tasks whose docs are still incomplete or partially templated` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus tests.test_golden`
- `Existing planning, MCP, evolution, and golden-template tests continue to pass after centralizing normalization` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus tests.test_mcp_server tests.test_mcp_core tests.test_mcp_adapter tests.test_evolution tests.test_golden`
- `Stale closed tasks are read back as workflow_phase=closed instead of preserving an outdated in-memory phase` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus tests.test_mcp_core`
- `Missing or partial plan sections do not crash task load/list projections` -> `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sisyphus tests.test_mcp_core`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
